import sqlite3
import bcrypt
import secrets
import hashlib
import difflib
import json
from datetime import datetime, timedelta
from typing import Optional, Tuple
from contextlib import contextmanager

DB_FILE = "users.db"


@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    conn = sqlite3.connect(DB_FILE, timeout=30.0)
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_database():
    """Initialize the SQLite database with users, sessions, evaluations, and comparisons tables"""
    # Enable WAL mode for better concurrency
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
    except Exception:
        pass

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Create users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token TEXT UNIQUE NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)

        # Create evaluations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                type TEXT NOT NULL,
                content TEXT,
                result TEXT NOT NULL,
                total_score INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)

        # Create comparisons table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS comparisons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                problem_statement TEXT NOT NULL,
                solution1_type TEXT NOT NULL,
                solution1_content TEXT NOT NULL,
                solution2_type TEXT NOT NULL,
                solution2_content TEXT NOT NULL,
                cfg1_json TEXT NOT NULL,
                cfg2_json TEXT NOT NULL,
                comparison_result TEXT NOT NULL,
                winner TEXT NOT NULL,
                overall_scores TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)

        # Create problems table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS problems (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                problem_statement TEXT NOT NULL,
                problem_hash TEXT UNIQUE NOT NULL,
                bottom_line_cfg TEXT,
                optimal_time_complexity TEXT,
                optimal_space_complexity TEXT,
                problem_category TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_problem_hash ON problems(problem_hash)"
        )

        # Create solutions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS solutions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                problem_id INTEGER NOT NULL,
                solution_type TEXT NOT NULL,
                solution_content TEXT NOT NULL,
                cfg_json TEXT NOT NULL,
                evaluation_score INTEGER,
                evaluation_result TEXT,
                is_reference_solution BOOLEAN DEFAULT 0,
                user_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (problem_id) REFERENCES problems (id),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)

        # Create AI response cache table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                call_type TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                response TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                hit_count INTEGER DEFAULT 0,
                UNIQUE(call_type, content_hash)
            )
        """)

        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_cache_lookup ON ai_cache(call_type, content_hash)"
        )

        conn.commit()


def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash"""
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def create_user(email: str, password: str) -> Tuple[bool, str]:
    """Create a new user. Returns (success, message)"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            password_hash = hash_password(password)
            cursor.execute(
                "INSERT INTO users (email, password_hash) VALUES (?, ?)",
                (email, password_hash),
            )
            conn.commit()
        return True, "User created successfully"
    except sqlite3.IntegrityError:
        return False, "User already exists"
    except Exception as e:
        return False, str(e)


def verify_user(email: str, password: str) -> Optional[int]:
    """Verify user credentials. Returns user_id if valid, None otherwise"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, password_hash FROM users WHERE email = ?", (email,)
            )
            result = cursor.fetchone()

            if result and verify_password(password, result[1]):
                return result[0]
            return None
    except Exception:
        return None


def create_session(user_id: int) -> str:
    """Create a new session for a user. Returns session token"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(days=7)

        cursor.execute(
            "INSERT INTO sessions (user_id, token, expires_at) VALUES (?, ?, ?)",
            (user_id, token, expires_at),
        )

        conn.commit()

    return token


def verify_session(token: str) -> Optional[int]:
    """Verify a session token. Returns user_id if valid, None otherwise"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT user_id FROM sessions WHERE token = ? AND expires_at > ?",
            (token, datetime.now()),
        )

        result = cursor.fetchone()

    return result[0] if result else None


def delete_session(token: str) -> bool:
    """Delete a session token. Returns True if successful"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("DELETE FROM sessions WHERE token = ?", (token,))

        success = cursor.rowcount > 0
        conn.commit()

    return success


def get_user_email(user_id: int) -> Optional[str]:
    """Get user email by user_id"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT email FROM users WHERE id = ?", (user_id,))

        result = cursor.fetchone()

    return result[0] if result else None


def save_evaluation(user_id: int, eval_type: str, content: str, result: dict) -> int:
    """Save an evaluation result. Returns evaluation_id"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO evaluations (user_id, type, content, result, total_score) VALUES (?, ?, ?, ?, ?)",
                (
                    user_id,
                    eval_type,
                    content,
                    json.dumps(result),
                    result.get("total_score", 0),
                ),
            )
            eval_id = cursor.lastrowid
            conn.commit()
            return eval_id
    except Exception:
        return 0


def get_user_evaluations(user_id: int, limit: int = 10):
    """Get recent evaluations for a user"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, type, content, result, total_score, created_at FROM evaluations WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit),
            )
            results = cursor.fetchall()

            evaluations = []
            for row in results:
                evaluations.append(
                    {
                        "id": row[0],
                        "type": row[1],
                        "content": row[2],
                        "result": json.loads(row[3]),
                        "total_score": row[4],
                        "created_at": row[5],
                    }
                )
            return evaluations
    except Exception:
        return []


def save_comparison(
    user_id: int,
    problem_statement: str,
    solution1_type: str,
    solution1_content: str,
    solution2_type: str,
    solution2_content: str,
    cfg1_json: str,
    cfg2_json: str,
    comparison_result: dict,
    winner: str,
    overall_scores: dict,
) -> int:
    """Save a solution comparison. Returns comparison_id"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO comparisons (user_id, problem_statement, solution1_type, solution1_content,
                   solution2_type, solution2_content, cfg1_json, cfg2_json, comparison_result, winner, overall_scores)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    user_id,
                    problem_statement,
                    solution1_type,
                    solution1_content[:1000],
                    solution2_type,
                    solution2_content[:1000],
                    cfg1_json,
                    cfg2_json,
                    json.dumps(comparison_result),
                    winner,
                    json.dumps(overall_scores),
                ),
            )
            comp_id = cursor.lastrowid
            conn.commit()
            return comp_id
    except Exception:
        return 0


def get_user_comparisons(user_id: int, limit: int = 20):
    """Get recent comparisons for a user"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT id, problem_statement, solution1_type, solution2_type, winner, 
                   overall_scores, comparison_result, created_at 
                   FROM comparisons WHERE user_id = ? ORDER BY created_at DESC LIMIT ?""",
                (user_id, limit),
            )
            results = cursor.fetchall()

            comparisons = []
            for row in results:
                comparisons.append(
                    {
                        "id": row[0],
                        "problem_statement": row[1],
                        "solution1_type": row[2],
                        "solution2_type": row[3],
                        "winner": row[4],
                        "overall_scores": json.loads(row[5]),
                        "comparison_result": json.loads(row[6]),
                        "created_at": row[7],
                    }
                )
            return comparisons
    except Exception:
        return []


def get_comparison_by_id(comparison_id: int, user_id: int):
    """Get a specific comparison by ID"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT id, problem_statement, solution1_type, solution1_content, solution2_type, 
                   solution2_content, cfg1_json, cfg2_json, comparison_result, winner, overall_scores, created_at
                   FROM comparisons WHERE id = ? AND user_id = ?""",
                (comparison_id, user_id),
            )
            row = cursor.fetchone()

            if not row:
                return None

            return {
                "id": row[0],
                "problem_statement": row[1],
                "solution1_type": row[2],
                "solution1_content": row[3],
                "solution2_type": row[4],
                "solution2_content": row[5],
                "cfg1_json": json.loads(row[6]),
                "cfg2_json": json.loads(row[7]),
                "comparison_result": json.loads(row[8]),
                "winner": row[9],
                "overall_scores": json.loads(row[10]),
                "created_at": row[11],
            }
    except Exception:
        return None


def normalize_problem_statement(statement: str) -> str:
    """Normalize problem statement for consistent hashing"""
    normalized = statement.lower().strip()
    normalized = " ".join(normalized.split())
    replacements = {
        "array": "list",
        "maximum": "max",
        "minimum": "min",
        "integer": "int",
        "string": "str",
    }
    for old, new in replacements.items():
        normalized = normalized.replace(old, new)
    return normalized


def hash_problem(statement: str) -> str:
    """Generate hash for problem statement"""
    normalized = normalize_problem_statement(statement)
    return hashlib.sha256(normalized.encode()).hexdigest()


def find_similar_problem(statement: str, threshold: float = 0.85):
    """Find similar problem in database"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, problem_statement, problem_hash, bottom_line_cfg FROM problems"
        )
        problems = cursor.fetchall()

        normalized_input = normalize_problem_statement(statement)
        best_match = None
        best_score = 0

        for problem in problems:
            normalized_existing = normalize_problem_statement(problem[1])
            similarity = difflib.SequenceMatcher(
                None, normalized_input, normalized_existing
            ).ratio()

            if similarity > best_score:
                best_score = similarity
                best_match = problem

        if best_score >= threshold:
            return {
                "id": best_match[0],
                "problem_statement": best_match[1],
                "problem_hash": best_match[2],
                "bottom_line_cfg": json.loads(best_match[3]) if best_match[3] else None,
                "similarity_score": best_score,
            }
        return None


def create_problem(statement: str) -> int:
    """Create new problem entry"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Reset sequence to current max id to ensure no gaps at the end
        cursor.execute(
            "UPDATE sqlite_sequence SET seq = (SELECT COALESCE(MAX(id), 0) FROM problems) WHERE name = 'problems'"
        )

        problem_hash = hash_problem(statement)
        cursor.execute(
            "INSERT INTO problems (problem_statement, problem_hash) VALUES (?, ?)",
            (statement, problem_hash),
        )
        conn.commit()
        return cursor.lastrowid


def update_problem_cfg(
    problem_id: int,
    bottom_line_cfg: dict,
    time_complexity: str,
    space_complexity: str,
    category: str = None,
):
    """Update problem with base-level CFG"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE problems SET bottom_line_cfg = ?, optimal_time_complexity = ?, 
               optimal_space_complexity = ?, problem_category = ?, updated_at = CURRENT_TIMESTAMP 
               WHERE id = ?""",
            (
                json.dumps(bottom_line_cfg),
                time_complexity,
                space_complexity,
                category,
                problem_id,
            ),
        )
        conn.commit()


def get_problem_by_id(problem_id: int):
    """Get problem by ID"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, problem_statement, bottom_line_cfg, optimal_time_complexity, optimal_space_complexity, problem_category FROM problems WHERE id = ?",
            (problem_id,),
        )
        row = cursor.fetchone()
        if row:
            return {
                "id": row[0],
                "problem_statement": row[1],
                "bottom_line_cfg": json.loads(row[2]) if row[2] else None,
                "optimal_time_complexity": row[3],
                "optimal_space_complexity": row[4],
                "problem_category": row[5],
            }
        return None


def save_solution(
    problem_id: int,
    solution_type: str,
    solution_content: str,
    cfg_json: dict,
    is_reference: bool = False,
    user_id: int = None,
    evaluation_score: int = None,
    evaluation_result: dict = None,
):
    """Save solution to database"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO solutions (problem_id, solution_type, solution_content, cfg_json, 
               is_reference_solution, user_id, evaluation_score, evaluation_result) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                problem_id,
                solution_type,
                solution_content[:5000],
                json.dumps(cfg_json),
                is_reference,
                user_id,
                evaluation_score,
                json.dumps(evaluation_result) if evaluation_result else None,
            ),
        )
        conn.commit()
        return cursor.lastrowid


def demote_reference_solutions(problem_id: int):
    """Demote all reference solutions for a problem to regular solutions"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE solutions SET is_reference_solution = 0 WHERE problem_id = ? AND is_reference_solution = 1",
            (problem_id,),
        )
        conn.commit()


def get_reference_solution(problem_id: int):
    """Get reference solution for a problem - returns the most recent reference"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT id, solution_type, solution_content, cfg_json FROM solutions 
               WHERE problem_id = ? AND is_reference_solution = 1 
               ORDER BY created_at DESC LIMIT 1""",
            (problem_id,),
        )
        row = cursor.fetchone()
        if row:
            return {
                "id": row[0],
                "solution_type": row[1],
                "solution_content": row[2],
                "cfg_json": json.loads(row[3]),
            }
        return None


def get_problem_solutions(problem_id: int, limit: int = 50):
    """Get all solutions for a problem"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT id, solution_type, evaluation_score, is_reference_solution, created_at 
               FROM solutions WHERE problem_id = ? ORDER BY created_at DESC LIMIT ?""",
            (problem_id, limit),
        )
        results = cursor.fetchall()
        return [
            {
                "id": r[0],
                "solution_type": r[1],
                "evaluation_score": r[2],
                "is_reference": bool(r[3]),
                "created_at": r[4],
            }
            for r in results
        ]


def search_problems(query: str, limit: int = 10):
    """Search for problems by statement or category"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        search_term = f"%{query}%"
        cursor.execute(
            """
            SELECT p.id, p.problem_statement, p.problem_category, p.created_at,
                   COUNT(s.id) as solution_count,
                   AVG(s.evaluation_score) as avg_score
            FROM problems p
            LEFT JOIN solutions s ON p.id = s.problem_id
            WHERE p.problem_statement LIKE ? OR p.problem_category LIKE ?
            GROUP BY p.id
            ORDER BY 
                CASE WHEN p.problem_statement LIKE ? THEN 1 ELSE 2 END,
                p.created_at DESC
            LIMIT ?
        """,
            (search_term, search_term, f"{query}%", limit),
        )
        results = cursor.fetchall()

        return [
            {
                "id": r[0],
                "problem_statement": r[1][:200] + "..." if len(r[1]) > 200 else r[1],
                "category": r[2],
                "created_at": r[3],
                "solution_count": r[4] or 0,
                "avg_score": round(r[5], 1) if r[5] else None,
            }
            for r in results
        ]


# Initialize database on module import
init_database()
