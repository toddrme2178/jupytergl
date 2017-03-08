// Copyright (c) Jupyter Development Team.
// Distributed under the terms of the Modified BSD License.

import {
  Kernel
} from '@jupyterlab/services';

import {
  DocumentRegistry, IDocumentRegistry,
} from 'jupyterlab/lib/docregistry';

import {
  ICommandPalette
} from 'jupyterlab/lib/commandpalette';

import {
  INotebookTracker, NotebookPanel
} from 'jupyterlab/lib/notebook';

import {
  JupyterLabPlugin, JupyterLab
} from 'jupyterlab/lib/application';

import {
  IDisposable, DisposableDelegate
} from '@phosphor/disposable';

import {
  Token
} from '@phosphor/application';

import {
  JupyterGLWidget, IJupyterGLWidget
} from './widget';


export
namespace CommandIDs {
  export
  const open: string = 'jupytergl:open';
};


/**
 * The widget manager provider.
 */
const service: JupyterLabPlugin<void> = {
  id: 'jupyter.extensions.jupyterGL',
  requires: [ICommandPalette, INotebookTracker],
  activate: activateWidgetExtension,
  autoStart: true
};

export default service;


/**
 * Activate the widget extension.
 */
function activateWidgetExtension(app: JupyterLab, palette: ICommandPalette, notebooks: INotebookTracker): void {
  const { commands, shell } = app;
  const category = 'JupyterGL';
  const command = CommandIDs.open;
  const label = 'Open JupyterGL';

  let view = new JupyterGLWidget();
  view.id = 'jp-jupytergl';
  view.title.label = 'JupyterGL';
  view.title.closable = true;

  // Create a handler for each notebook that is created.
  notebooks.widgetAdded.connect((sender, parent) => {
    const kernel = parent.kernel;

    view.source = kernel;

     // Listen for kernel changes.
     parent.kernelChanged.connect((sender, kernel) => {
       view.source = kernel;
    });
  });

  // Keep track of notebook instances and set inspector source.
  app.shell.currentChanged.connect((sender, args) => {
    let widget = args.newValue;
    if (!widget || !notebooks.has(widget)) {
      return;
    }
    let nbPanel = widget as NotebookPanel;
    let source = nbPanel.kernel;
    if (source) {
      view.source = source;
    }
  });

  // Add command to registry and palette.
  commands.addCommand(command, {
    label,
    execute: () => {
      if (!view.isAttached) {
        shell.addToMainArea(view);
      }
      if (view.isAttached) {
        view.activate();
      }
    }
  });
  palette.addItem({ command, category });
}
