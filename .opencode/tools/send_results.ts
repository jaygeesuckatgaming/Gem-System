// .opencode/tools/send_results.ts
import { tool } from "@opencode-ai/plugin";

export default tool({
  description: "Send the final execution results, summary, or outputs back to the Gem-System MCP.",
  args: {
    sessionId: tool.schema.string().describe("The active OpenCode session ID"),
    status: tool.schema.enum(["success", "failed"]).describe("The final status of the task"),
    output: tool.schema.string().describe("The generated summary, code changes, or errors to report back")
  },
  async run({ sessionId, status, output }) {
    try {
      const response = await fetch("http://localhost:5000/opencode/webhook", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ sessionId, status, output })
      });

      if (!response.ok) {
        return { success: false, error: `MCP returned status ${response.status}` };
      }

      return { success: true, message: "Results successfully delivered to Gem-System MCP." };
    } catch (err: any) {
      return { success: false, error: err.message };
    }
  }
});
