

export
function availableMethods(gl: WebGLRenderingContext): string[] {
  let ret: string[] = [];
  for (let key in gl) {
    if (typeof (gl as any)[key] === 'function') {
      ret.push(key);
    }
  }
  return ret;
}


const nonConstKeys = ['drawingBufferWidth', 'drawingBufferHeight'];

export
function availableConstants(gl: WebGLRenderingContext): string[] {
  let ret: string[] = [];
  for (let key in gl) {
    if (nonConstKeys.indexOf(key) !== -1) {
      continue;
    } else if (typeof (gl as any)[key] === 'number') {
      ret.push(key);
    }
  }
  return ret;
}
