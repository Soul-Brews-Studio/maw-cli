import { checkoutGit } from "./mod.checkoutGit";
import { devCalver } from "./mod.devCalver";
import { shellQuote } from "./mod.shellQuote";

// A dev build running from a git checkout of this repository updates the
// checkout by fast-forward only: fetch origin, then `merge --ff-only` the
// current branch's upstream, or, for `alpha`, switch to alpha and fast-forward
// it from origin/alpha. It never forces, resets or stashes. A dirty tree is
// refused before anything runs; diverged or upstream-less branches are refused
// after the fetch with the command that inspects them. --check fetches and
// reports, leaving the branch and the tree alone.
export function updateCheckout(root: string, branch: string, channel: string, check: boolean): number {
  const q = shellQuote(root);
  const git = (args: string[], optional = false, timeout?: number) => checkoutGit(root, args, optional, timeout);
  const refuse = (message: string, ...fix: string[]) => {
    console.error(`maw: update: ${message}`);
    for (const line of fix) console.error(`  ${line}`);
    return 1;
  };
  const running = () => {
    const detail = devCalver();
    return detail ? `dev ${detail}` : "dev";
  };
  try {
    if (!check && git(["status", "--porcelain"]) !== "") return refuse(`${root} has uncommitted changes; maw touches nothing in a dirty tree`, `git -C ${q} status`);
    try { git(["fetch", "--quiet", "origin"], false, 120_000); }
    catch (error) { return refuse((error as Error).message, `git -C ${q} fetch origin`); }
    let local = "HEAD", target: string, switchFrom = "";
    if (channel === "alpha") {
      target = "origin/alpha";
      if (!git(["rev-parse", "--verify", "--quiet", "refs/remotes/origin/alpha^{commit}"], true)) return refuse("origin has no alpha branch", `git -C ${q} ls-remote --heads origin alpha`);
      if (branch !== "alpha") {
        switchFrom = branch || "detached HEAD";
        // `git switch alpha` creates alpha at origin/alpha when there is no local alpha yet.
        local = git(["rev-parse", "--verify", "--quiet", "refs/heads/alpha^{commit}"], true) ? "alpha" : "";
      }
    } else {
      if (!branch) return refuse("detached HEAD has no upstream to fast-forward from", "maw update alpha");
      target = git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"], true);
      if (!target) {
        const fix = ["maw update alpha"];
        if (git(["rev-parse", "--verify", "--quiet", `refs/remotes/origin/${branch}^{commit}`], true)) fix.unshift(`git -C ${q} branch --set-upstream-to=origin/${branch}`);
        return refuse(`${branch} has no upstream to fast-forward from`, ...fix);
      }
    }
    const [ahead, behind] = local ? git(["rev-list", "--left-right", "--count", `${local}...${target}`]).split(/\s+/).map(Number) : [0, 0];
    let status = ahead && behind ? `diverged from ${target} (${ahead} ahead, ${behind} behind); fast-forward impossible`
      : behind ? `update available: behind ${target} by ${behind}`
      : ahead ? `ahead of ${target} by ${ahead}; nothing to fast-forward`
      : "already up to date";
    if (switchFrom) status = `switch ${switchFrom} -> alpha; ${status}`;
    process.stdout.write(`current\t${running()}\ntarget\t${target}\ncommit\t${git(["rev-parse", `${target}^{commit}`])}\nstatus\t${status}\n`);
    if (check) return 0;
    if (ahead && behind) {
      const range = channel ? `${local}...${target}` : "HEAD...@{upstream}";
      return refuse(`${local === "HEAD" ? branch : local} has diverged from ${target}; maw only fast-forwards`, `git -C ${q} log --oneline --left-right ${range}`);
    }
    if (switchFrom) git(["switch", "--quiet", "alpha"]);
    if (behind) git(["merge", "--ff-only", "--quiet", target]);
    if (switchFrom || behind) process.stdout.write(`updated\t${running()}\n`);
    return 0;
  } catch (error) {
    return refuse((error as Error).message, `git -C ${q} status`);
  }
}
