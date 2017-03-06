
import {
  JSONArray, JSONValue, JSONPrimitive
} from './json';

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


export
interface IInstruction {
  type: 'exec' | 'query';
  op: string;
  args: JSONArray;
}


export
function execMessage(gl: WebGLRenderingContext, message: IInstruction[]): void {
  for (let instruction of message) {
    execInstruction(gl, instruction);
  }
}


export
function queryMessage(gl: WebGLRenderingContext, message: IInstruction[]): void {
  for (let i = 0; i < message.length - 1; ++i) {
    execInstruction(gl, message[i]);
  }
  return queryInstruction(gl, message[message.length - 1]);
}


/**
 * Execute an instruction, discarding any return value.
 *
 * Throws an error if instruction is missing.
 */
function execInstruction(gl: WebGLRenderingContext, instruction: IInstruction): void {
  (gl as any)[instruction.op](...instruction.args);
}


/**
 * Process an instruction, returning its return value.
 *
 * Throws an error if instruction is missing.
 */
function queryInstruction(gl: WebGLRenderingContext, instruction: IInstruction): void {
  return (gl as any)[instruction.op](...instruction.args);
}
