// Copyright (c) Jupyter Development Team.
// Distributed under the terms of the Modified BSD License.

import {
  Kernel
} from '@jupyterlab/services';

import {
  Token
} from '@phosphor/application';

import {
  Panel, TabPanel, Widget
} from '@phosphor/widgets';

import {
  Context, startCommListen
} from 'jupytergl/lib';


const GLVIEW_CLASS = 'jpGL-view';
const GLITEM_CLASS = 'jpGL-item';


/**
 * The inspector panel token.
 */
export
const IJupyterGLWidget = new Token<IJupyterGLWidget>('jupyter.extensions.jupyterGLWidget');


/**
 * An interface for an inspector panel.
 */
export
interface IJupyterGLWidget {
    source: Kernel.IKernel | null;
    readonly context: Context | null;
}


/**
 * A panel which contains a set of WebGL canvases.
 */
export
class JupyterGLWidget extends TabPanel implements IJupyterGLWidget {
  /**
   *
   */
  constructor() {
    super();
    this.addClass(GLVIEW_CLASS);
  }

  get source(): Kernel.IKernel | null {
    if (this._source === null) {
      return null;
    }
    return this._source;
  }

  set source(kernel: Kernel.IKernel | null) {
    if (kernel === this._source) {
      return;
    }
    this._source = kernel;
    this.updateView();
  }

  get context(): Context | null {
    if (this._source === null) {
      return null;
    }
    return this.items[this._source.id].context;
  }

  protected clear(): void {
    this.widgets.forEach(widget => widget.dispose());
  }

  protected updateView(): void {
    let source = this._source;
    if (source === null) {
      this.clear();
    } else if (this.items.hasOwnProperty(source.id)) {
      let widget = this.items[source.id];
      if (this.widgets.indexOf(widget) === -1) {
        // Not currently shown
        this.clear();
        this.addWidget(widget);
      }
    } else {
      // Create new items
      let widget = new JupyterGLItem(source);
      source.terminated.connect((sender) => {
        // Ensure it is removed when kernel is terminated
        if (this._source === source) {
          this._source = null;
          this.updateView();
        }
        this.items[sender.id].dispose();
        delete this.items[sender.id];
      });
      this.items[source.id] = widget;
      this.clear();
      this.addWidget(widget);
    }
  }

  protected items: { [key: string]: JupyterGLItem } = {};

  private _source: Kernel.IKernel | null = null;
}


export
class JupyterGLItem extends Widget {
  /**
   *
   */
  constructor(kernel: Kernel.IKernel) {
    super();
    this.addClass(GLITEM_CLASS);
    this.context = new Context(this.node);
    startCommListen(kernel, this.context.handleMessage.bind(this.context));
  }

  readonly context: Context;
}
