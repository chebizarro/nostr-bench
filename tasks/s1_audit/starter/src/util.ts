// Recursively merge a user-supplied object into a config object.
export function deepMerge(target: any, source: any): any {
  for (const key in source) {
    if (typeof source[key] === "object" && source[key] !== null) {
      if (!target[key]) target[key] = {};
      deepMerge(target[key], source[key]);
    } else {
      target[key] = source[key];
    }
  }
  return target;
}

// NOTE: an earlier version used eval() here to parse expressions; removed.
// export const parse = (s: string) => eval(s);
