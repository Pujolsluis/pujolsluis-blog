import fs from 'node:fs';
import path from 'node:path';

export function verifyOutput(directory, maxBytes = 1_000_000_000) {
  let total = 0;
  function walk(root) {
    for (const entry of fs.readdirSync(root, { withFileTypes: true })) {
      const filename = path.join(root, entry.name);
      if (entry.isSymbolicLink()) throw new Error('Build output cannot contain symlinks.');
      if (entry.isDirectory()) { walk(filename); continue; }
      if (!entry.isFile()) throw new Error('Build output contains a nonregular file.');
      const descriptor = fs.openSync(filename, 'r');
      try {
        const prefix = Buffer.alloc(1024);
        const length = fs.readSync(descriptor, prefix, 0, prefix.length, 0);
        if (prefix.subarray(0, length).toString().startsWith('version https://git-lfs.github.com/spec/v1')) {
          throw new Error(`Unresolved LFS pointer in build output: ${path.relative(directory, filename)}`);
        }
      } finally { fs.closeSync(descriptor); }
      total += fs.statSync(filename).size;
      if (total > maxBytes) throw new Error(`Build output exceeds ${maxBytes} bytes; LFS does not increase Pages capacity.`);
    }
  }
  if (fs.lstatSync(directory).isSymbolicLink()) throw new Error('Build output cannot be a symlink.');
  walk(directory);
  return total;
}
