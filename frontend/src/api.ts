export async function api<T>(
  path: string,
  body?: unknown,
  method = "POST",
): Promise<T> {
  const response = await fetch(
    `/api${path}`,
    body === undefined
      ? {}
      : {
          method,
          headers:
            body instanceof FormData
              ? undefined
              : { "Content-Type": "application/json" },
          body: body instanceof FormData ? body : JSON.stringify(body),
        },
  );
  const result = await response.json();
  if (!response.ok) {
    const details = (result.details ?? [])
      .map(
        (d: { row?: number; field?: string; message: string }) =>
          `${d.row ? `Row ${d.row}: ` : ""}${d.field ? `${d.field}: ` : ""}${d.message}`,
      )
      .join("\n");
    throw new Error(
      `${result.message ?? "Request failed"}${details ? `\n${details}` : ""}`,
    );
  }
  return result as T;
}
