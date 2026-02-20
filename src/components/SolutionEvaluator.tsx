import { useState, useEffect } from "react";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./ui/tabs";
import { Textarea } from "./ui/textarea";
import { Progress } from "./ui/progress";
import { Badge } from "./ui/badge";
import { Label } from "./ui/label";
import { Dialog, DialogContent } from "./ui/dialog";
import { toast } from "sonner";
import { api } from "../lib/api";
import { ImagePlus, FileCode2, X, ZoomIn, FileText } from "lucide-react";

interface SolutionEvaluatorProps {
  problemId: number | null;
  hasReference: boolean;
}

export default function SolutionEvaluator({
  problemId,
  hasReference,
}: SolutionEvaluatorProps) {
  const [loading, setLoading] = useState(false);
  const [solutionType, setSolutionType] = useState<"flowchart" | "pseudocode">(
    "pseudocode"
  );
  const [pseudocode, setPseudocode] = useState("");
  const [flowchartImage, setFlowchartImage] = useState("");
  const [flowchartIsPdf, setFlowchartIsPdf] = useState(false);
  const [evaluation, setEvaluation] = useState<any>(null);
  const [zoomedDiagram, setZoomedDiagram] = useState<{
    svg: string;
    code: string;
  } | null>(null);

  useEffect(() => {
    if (
      evaluation?.mermaid_diagrams?.user &&
      evaluation?.mermaid_diagrams?.reference
    ) {
      const renderMermaid = async () => {
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({ startOnLoad: false, theme: "default" });

        setTimeout(() => {
          mermaid.run().catch((err) => console.error("Mermaid error:", err));
        }, 100);
      };
      renderMermaid();
    }
  }, [evaluation, zoomedDiagram]);

  const handleEvaluate = async () => {
    if (!problemId) {
      toast.error("Please upload a problem first");
      return;
    }

    if (!hasReference) {
      toast.error("No reference solution available for this problem");
      return;
    }

    const content = solutionType === "pseudocode" ? pseudocode : flowchartImage;
    if (!content.trim()) {
      toast.error("Please provide your solution");
      return;
    }

    setLoading(true);
    try {
      const response = await api.post("/evaluate-solution", {
        problem_id: problemId,
        solution_type: solutionType,
        solution_content: content,
        content_format:
          flowchartIsPdf && solutionType === "flowchart" ? "pdf" : undefined,
      });
      const data = await response.json();

      setEvaluation({ ...data, _ts: Date.now() });
      toast.success(`Evaluation complete! Score: ${data.total_score}/100`);
    } catch (error: any) {
      toast.error(error.message || "Failed to evaluate solution");
    } finally {
      setLoading(false);
    }
  };

  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const isPdf =
        file.type === "application/pdf" ||
        file.name.toLowerCase().endsWith(".pdf");
      setFlowchartIsPdf(isPdf);
      const reader = new FileReader();
      reader.onloadend = () => {
        setFlowchartImage(reader.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Your Solution</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <Tabs
          value={solutionType}
          onValueChange={(v) => setSolutionType(v as any)}
        >
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="pseudocode" className="gap-2">
              <FileCode2 className="h-4 w-4" />
              Pseudocode
            </TabsTrigger>
            <TabsTrigger value="flowchart" className="gap-2">
              <ImagePlus className="h-4 w-4" />
              Flowchart
            </TabsTrigger>
          </TabsList>

          <TabsContent value="pseudocode" className="space-y-2">
            <Label>Enter Pseudocode</Label>
            <Textarea
              placeholder="Enter your pseudocode solution..."
              value={pseudocode}
              onChange={(e) => setPseudocode(e.target.value)}
              rows={10}
              className="font-mono text-sm"
            />
          </TabsContent>

          <TabsContent value="flowchart" className="space-y-4">
            <Label>Upload Flowchart Image</Label>
            {!flowchartImage ? (
              <div className="border-2 border-dashed border-border rounded-lg p-8 text-center hover:border-primary transition-colors">
                <input
                  type="file"
                  id="flowchart-upload"
                  accept="image/*,.pdf"
                  onChange={handleImageUpload}
                  className="hidden"
                />
                <label htmlFor="flowchart-upload" className="cursor-pointer">
                  <ImagePlus className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
                  <p className="text-sm text-muted-foreground">
                    Click to upload flowchart image
                  </p>
                  <p className="text-xs text-muted-foreground mt-2">
                    PNG, JPG, JPEG, PDF (max 5MB)
                  </p>
                </label>
              </div>
            ) : (
              <div className="relative border border-border rounded-lg p-4">
                <Button
                  variant="destructive"
                  size="icon"
                  className="absolute top-2 right-2 z-10"
                  onClick={() => {
                    setFlowchartImage("");
                    setFlowchartIsPdf(false);
                  }}
                >
                  <X className="h-4 w-4" />
                </Button>
                {flowchartIsPdf ? (
                  <div className="flex flex-col items-center justify-center py-8">
                    <FileText className="h-16 w-16 text-primary mb-2" />
                    <p className="text-sm text-muted-foreground">
                      PDF file uploaded
                    </p>
                  </div>
                ) : (
                  <img
                    src={flowchartImage}
                    alt="Your flowchart"
                    className="max-w-full h-auto mx-auto rounded"
                  />
                )}
              </div>
            )}
          </TabsContent>
        </Tabs>

        <Button
          onClick={handleEvaluate}
          disabled={!problemId || !hasReference || loading}
          className="w-full"
        >
          {loading ? "Evaluating..." : "Evaluate Solution"}
        </Button>

        {evaluation && (
          <div className="space-y-4 mt-6">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold">Evaluation Results</h3>
              <Badge
                variant={
                  evaluation.total_score >= 70 ? "default" : "destructive"
                }
              >
                {evaluation.total_score}/100
              </Badge>
            </div>

            <div className="space-y-3">
              {Object.entries(evaluation.breakdown).map(
                ([key, value]: [string, any]) => (
                  <div key={key} className="space-y-1">
                    <div className="flex justify-between text-sm">
                      <span className="capitalize">
                        {key.replace(/_/g, " ")}
                      </span>
                      <span>
                        {value.score}/
                        {key === "structural_similarity"
                          ? 40
                          : key === "control_flow_coverage"
                          ? 30
                          : key === "correctness"
                          ? 20
                          : 10}
                      </span>
                    </div>
                    <Progress
                      value={
                        (value.score /
                          (key === "structural_similarity"
                            ? 40
                            : key === "control_flow_coverage"
                            ? 30
                            : key === "correctness"
                            ? 20
                            : 10)) *
                        100
                      }
                    />
                    <p className="text-xs text-muted-foreground">
                      {value.feedback}
                    </p>
                  </div>
                )
              )}
            </div>

            {evaluation.cfg_comparison?.differences?.length > 0 && (
              <div className="space-y-2">
                <h4 className="font-semibold text-sm">Differences:</h4>
                <ul className="list-disc list-inside text-sm space-y-1">
                  {evaluation.cfg_comparison.differences.map(
                    (diff: string, i: number) => (
                      <li key={i} className="text-muted-foreground">
                        {diff}
                      </li>
                    )
                  )}
                </ul>
              </div>
            )}

            {evaluation.recommendations?.length > 0 && (
              <div className="space-y-2">
                <h4 className="font-semibold text-sm">Recommendations:</h4>
                <ul className="list-disc list-inside text-sm space-y-1">
                  {evaluation.recommendations.map((rec: string, i: number) => (
                    <li key={i} className="text-blue-600">
                      {rec}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {evaluation.mermaid_diagrams &&
              evaluation.mermaid_diagrams.user &&
              evaluation.mermaid_diagrams.reference && (
                <div className="mt-6 space-y-4">
                  <h3 className="text-lg font-bold text-card-foreground">
                    CFG Comparison
                  </h3>
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    <Card className="border-blue-500/50 bg-gradient-to-br from-blue-500/5 to-blue-500/10">
                      <CardHeader className="pb-3">
                        <CardTitle className="text-sm text-blue-600 dark:text-blue-400 flex items-center justify-between">
                          Your Solution
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={async () => {
                              const mermaid = (await import("mermaid")).default;
                              const { svg } = await mermaid.render(
                                "zoomed-user",
                                evaluation.mermaid_diagrams.user
                              );
                              setZoomedDiagram({
                                svg,
                                code: evaluation.mermaid_diagrams.user,
                              });
                            }}
                          >
                            <ZoomIn className="h-4 w-4" />
                          </Button>
                        </CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div
                          className="p-4 bg-background rounded-lg overflow-auto border border-blue-500/30 max-h-[500px] cursor-pointer"
                          onClick={async () => {
                            const mermaid = (await import("mermaid")).default;
                            const { svg } = await mermaid.render(
                              "zoomed-user-click",
                              evaluation.mermaid_diagrams.user
                            );
                            setZoomedDiagram({
                              svg,
                              code: evaluation.mermaid_diagrams.user,
                            });
                          }}
                        >
                          <div
                            className="mermaid"
                            key={`user-mermaid-${evaluation.evaluation_id}-${evaluation._ts}`}
                          >
                            {evaluation.mermaid_diagrams.user}
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                    <Card className="border-green-500/50 bg-gradient-to-br from-green-500/5 to-green-500/10">
                      <CardHeader className="pb-3">
                        <CardTitle className="text-sm text-green-600 dark:text-green-400 flex items-center justify-between">
                          Reference Solution
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={async () => {
                              const mermaid = (await import("mermaid")).default;
                              const { svg } = await mermaid.render(
                                "zoomed-ref",
                                evaluation.mermaid_diagrams.reference
                              );
                              setZoomedDiagram({
                                svg,
                                code: evaluation.mermaid_diagrams.reference,
                              });
                            }}
                          >
                            <ZoomIn className="h-4 w-4" />
                          </Button>
                        </CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div
                          className="p-4 bg-background rounded-lg overflow-auto border border-green-500/30 max-h-[500px] cursor-pointer"
                          onClick={async () => {
                            const mermaid = (await import("mermaid")).default;
                            const { svg } = await mermaid.render(
                              "zoomed-ref-click",
                              evaluation.mermaid_diagrams.reference
                            );
                            setZoomedDiagram({
                              svg,
                              code: evaluation.mermaid_diagrams.reference,
                            });
                          }}
                        >
                          <div
                            className="mermaid"
                            key={`ref-mermaid-${evaluation.evaluation_id}-${evaluation._ts}`}
                          >
                            {evaluation.mermaid_diagrams.reference}
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  </div>

                  <Dialog
                    open={!!zoomedDiagram}
                    onOpenChange={() => setZoomedDiagram(null)}
                  >
                    <DialogContent className="max-w-[95vw] max-h-[95vh] overflow-hidden flex flex-col">
                      <div className="flex-1 overflow-auto p-8">
                        <div
                          className="flex items-center justify-center min-h-full"
                          dangerouslySetInnerHTML={{
                            __html: zoomedDiagram?.svg || "",
                          }}
                        />
                      </div>
                    </DialogContent>
                  </Dialog>
                </div>
              )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
