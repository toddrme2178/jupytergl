

import {
  Kernel, KernelMessage
} from '@jupyterlab/services';

import {
  JSONArray, JSONValue, JSONPrimitive, JSONObject
} from './json';

import {
  IMessage, IReply, IConstantsReply, IMethodsReply, IQueryReply
} from './comm';


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
function availableConstants(gl: WebGLRenderingContext): {[key: string]: number} {
  let ret: {[key: string]: number} = {};
  for (let key in gl) {
    if (nonConstKeys.indexOf(key) !== -1) {
      continue;
    } else if (typeof (gl as any)[key] === 'number') {
      ret[key] == (gl as any)[key];
    }
  }
  return ret;
}


export
interface IInstruction extends JSONObject {
  type: 'exec' | 'query';
  op: string;
  args: JSONArray;
}


export
type Buffer = ArrayBuffer | ArrayBufferView;


type BufferTypeKey =   'uint8' | 'int8' | 'uint8C' | 'int16' | 'uint16' | 'int32' | 'uint32' | 'float32' | 'float64';
const bufferViewMap = {
  'uint8': Uint8Array,
  'int8': Int8Array,
  'uint8C': Uint8ClampedArray,
  'int16': Int16Array,
  'uint16': Uint16Array,
  'int32': Int32Array,
  'uint32': Uint32Array,
  'float32': Float32Array,
  'float64': Float64Array
}


export
class Context {
  /**
   *
   */
  constructor(canvas: HTMLCanvasElement) {
    let context = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
    if (context === null) {
      throw TypeError('Could not get WebGL context for canvas!');
    }
    this.context = context;
    this.variables = {};
  }


  protected messageBufferContext(buffers: Buffer[], inner: () => void): void {
    try {
      this._currentBuffers = buffers;
      inner();
    } finally {
      this._currentBuffers = null;
    }
  }


  handleMessage(comm: Kernel.IComm, message: KernelMessage.ICommMsgMsg): void {
    let data = message.content.data as IMessage;
    if (data.type === 'exec') {
      let instructions = data.instructions;
      this.messageBufferContext(message.buffers, () => {
        this.execMessage(this.context, instructions);
      });
    } else if (data.type === 'query') {
      let instructions = data.instructions;
      this.messageBufferContext(message.buffers, () => {
        let result = this.queryMessage(this.context, instructions);
        let reply: IQueryReply = {
          type: 'queryReply',
          data: result
        };
        comm.open();
        comm.send(reply)
        comm.close();
      });
    } else if (data.type === 'getConstants' || data.type === 'getMethods') {
      if (data.target === 'context') {
        let reply: IReply;
        if (data.type === 'getConstants') {
          let constants = availableConstants(this.context);
          reply = {
            type: 'constantsReply',
            target: data.target,
            data: constants
          }
        } else {
          let methods = availableMethods(this.context);
          reply = {
            type: 'methodsReply',
            target: data.target,
            data: methods
          }
        }
        comm.open();
        comm.send(reply)
        comm.close();
      }
    }
  }

  execMessage(gl: WebGLRenderingContext, message: IInstruction[]): void {
    for (let instruction of message) {
      this.execInstruction(gl, instruction);
    }
  }



  queryMessage(gl: WebGLRenderingContext, message: IInstruction[]): JSONValue {
    for (let i = 0; i < message.length - 1; ++i) {
      this.execInstruction(gl, message[i]);
    }
    return this.queryInstruction(gl, message[message.length - 1]);
  }


  protected expandArgs(args: JSONArray): any[] {
    let ret: any[] = [];
    for (let arg of args) {
      if (typeof arg === 'string') {
        if (arg.slice(0, 6) === 'buffer') {
          let bufType = arg.slice(6) as BufferTypeKey;
          let raw = this._currentBuffers!.shift()!;
          if (ArrayBuffer.isView(raw)) {
            raw = raw.buffer;
          }
          let view = new bufferViewMap[bufType](raw);
          ret.push(view);
        } else {
          ret.push(this.variables[arg]);
        }
      } else {
        ret.push(arg);
      }
    }
    return ret;
  }


  /**
   * Execute an instruction, discarding any return value.
   *
   * Throws an error if instruction is missing.
   */
  protected execInstruction(gl: WebGLRenderingContext, instruction: IInstruction): void {
    (gl as any)[instruction.op](...this.expandArgs(instruction.args));
  }


  /**
   * Process an instruction, returning its return value.
   *
   * Throws an error if instruction is missing.
   */
  protected queryInstruction(gl: WebGLRenderingContext, instruction: IInstruction): JSONValue {
    let result = (gl as any)[instruction.op](...this.expandArgs(instruction.args));
    if (result === undefined) {
      throw TypeError('Result of query was undefined!');
    }
    if (result === null || typeof result === 'string' || typeof result === 'number' || typeof result === 'boolean') {
      return result as JSONPrimitive;
    }
    // We have received a reference that needs to be stored locally.
    let key = 'key' + this.variableIdGen++;
    this.variables[key] = result;
    return key;
  }

  context: WebGLRenderingContext;

  protected variables: {[key: string]: any};

  protected variableIdGen = 1;

  private _currentBuffers: Buffer[] | null = null;
}
