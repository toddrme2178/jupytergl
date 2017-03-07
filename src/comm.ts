
import {
  ContentsManager, Kernel, Session, KernelMessage
} from '@jupyterlab/services';

import {
  JSONArray, JSONValue, JSONPrimitive, JSONObject
} from './json';

import {
  execMessage, queryMessage, IInstruction
} from '.'



export
function setupComm(options: {kernel: Kernel.IKernel,
                   onMessage: (comm: Kernel.IComm, message: KernelMessage.ICommMsgMsg) => void,
                   onOpen?: (comm: Kernel.IComm, message: KernelMessage.ICommOpenMsg) => void,
                   onClose?: (comm: Kernel.IComm, message: KernelMessage.ICommCloseMsg) => void,
                   }): Promise<void> {
  let {kernel, onMessage, onOpen, onClose} = options;
  return new Promise<void>((resolve, reject) => {
    kernel.registerCommTarget('jupytergl', (comm, openMessage) => {
      if (openMessage.content.target_name !== 'jupytergl') {
        reject('Could not initialize comm!');
      }
      comm.onMsg = (msg) => {
        onMessage(comm, msg);
      };
      if (onClose !== undefined) {
        comm.onClose = (msg) => {
          onClose!(comm, msg);
        }
      }
      if (onOpen) {
        onOpen(comm, openMessage);
      }
      resolve();
    });
  });
}


export
function startCommListen(kernel: Kernel.IKernel,
                         handleMessage: (comm: Kernel.IComm, message: KernelMessage.ICommMsgMsg) => void
                         ): Promise<void> {

  return new Promise<void>((resolve) => {
    let setup = setupComm({kernel,
      onOpen: (comm, message) => {
        handleMessage(comm, message);
      },
      onMessage: (comm, message) => {
        handleMessage(comm, message);
      },
      onClose: (comm, message) => {
        handleMessage(comm, message);
        comm.dispose();
        resolve();
      }
    });
  });
}


export
interface IInstructionMessage extends JSONObject {
  type: 'exec' | 'query';
  instructions: IInstruction[];
}

export
interface IInspectMessage extends JSONObject {
  type: 'getConstants' | 'getMethods';
  target: 'context';
}

export
interface IConstantsReply extends JSONObject {
  type: 'constantsReply';
  target: 'context';
  data: {
    [key: string]: number;
  }
}

export
interface IMethodsReply extends JSONObject {
  type: 'methodsReply';
  target: 'context';
  data: string[];
}

export
interface IQueryReply extends JSONObject {
  type: 'queryReply';
  data: JSONValue;
}

export
type IInspectReply = IConstantsReply | IMethodsReply;

export
type IReply = IInspectReply;

export
type IMessage = IInstructionMessage | IInspectMessage;

