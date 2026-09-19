export type Command = {
  name: string;
  summary: string;
  usage?: string;
  path?: string;
  run: (args: string[]) => number | Promise<number>;
};
