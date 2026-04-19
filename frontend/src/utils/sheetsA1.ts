/** Индекс колонки 0-based → буквы A, B, …, Z, AA, … */
export function colIndexToLetters(indexZeroBased: number): string {
  let n = indexZeroBased + 1;
  let s = "";
  while (n > 0) {
    const m = (n - 1) % 26;
    s = String.fromCharCode(65 + m) + s;
    n = Math.floor((n - 1) / 26);
  }
  return s;
}

/** Имя листа для A1: 'Имя с пробелом'!A1 */
export function quoteSheetName(name: string): string {
  return `'${name.replace(/'/g, "''")}'`;
}
