export async function execute(path: string, args: string[], env?: Record<string, string>): Promise<number> {
  try {
    const child = Bun.spawn([path, ...args], {
      stdin: "inherit",
      stdout: "inherit",
      stderr: "inherit",
      env: env ? { ...process.env, ...env } : process.env,
    });
    let interrupted = false;
    const interrupt = () => {
      interrupted = true;
      child.kill("SIGKILL");
    };
    process.on("SIGINT", interrupt);
    try {
      const code = await child.exited;
      return interrupted ? 1 : child.signalCode ? 126 : code;
    } finally {
      process.off("SIGINT", interrupt);
    }
  } catch (error) {
    console.error(`maw: cannot execute ${path}: ${error instanceof Error ? error.message : error}`);
    return 126;
  }
}
