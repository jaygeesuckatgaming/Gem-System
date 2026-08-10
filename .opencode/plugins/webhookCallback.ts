// .opencode/plugins/webhookCallback.ts
export default function webhookCallbackPlugin(ctx: any) {
  // Hook into the end of a session execution
  ctx.session.hook("end", async (sessionInfo: any) => {
    try {
      // Get the session details
      const sessionId = sessionInfo.id || "unknown";
      const status = sessionInfo.exitCode === 0 ? "success" : "failed";
      
      // Create a summary from the session
      const output = sessionInfo.summary 
        ? `Files changed: ${sessionInfo.summary.files || 0}, Summary: ${JSON.stringify(sessionInfo.summary)}`
        : "Session completed";
      
      await fetch("http://localhost:5000/opencode/webhook", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          sessionId,
          status,
          output
        })
      });
      
      console.log(`✅ Sent results to MCP for session ${sessionId}`);
    } catch (err: any) {
      console.error("❌ Failed to send webhook to MCP:", err.message);
    }
  });
}
