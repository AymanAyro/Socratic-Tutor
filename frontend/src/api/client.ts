const API = "/api/v1";

export function apiUrl(path: string): string {
  return `${API}${path.startsWith("/") ? path : `/${path}`}`;
}

export async function parseSSE(
  response: Response,
  onEvent: (event: string, data: string) => void
): Promise<void> {
  const reader = response.body?.getReader();
  if (!reader) return;
  const decoder = new TextDecoder();
  let buffer = "";
  let eventName = "message";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";
    for (const block of parts) {
      let dataLine = "";
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) eventName = line.slice(6).trim();
        else if (line.startsWith("data:")) dataLine = line.slice(5).trim();
      }
      if (dataLine) onEvent(eventName, dataLine);
      eventName = "message";
    }
  }
}
