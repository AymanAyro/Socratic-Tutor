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
      const dataLines: string[] = [];
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) eventName = line.slice(6).trim();
        else if (line.startsWith("data:")) {
          let data = line.slice(5);
          if (data.startsWith(" ")) data = data.slice(1);
          dataLines.push(data);
        }
      }
      const dataLine = dataLines.join("\n");
      if (dataLine) onEvent(eventName, dataLine);
      eventName = "message";
    }
  }
}
