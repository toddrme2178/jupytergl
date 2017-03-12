
import {
  Context
} from '.';

import {
  JSONValue
} from './json';

import * as THREE from 'three';
import { OrbitControls } from 'three-orbitcontrols-ts';


export
function threeOrbit(context: Context, args: JSONValue[], renderCallback?: () => void): void {
  let fov = args[0] as number || 60;
  let near = args[1] as number || 1;
  let far = args[2] as number || 1000;
  let view = new ThreeOrbitView(context, fov, near, far, renderCallback);
}


class ThreeOrbitView {
  constructor(context: Context, fov: number, near: number, far: number, renderCallback?: () => void) {
    this.context = context;
    let gl = context.context;
    let canvas = gl.canvas;
    this.renderCallback = renderCallback;

    // When you need to set the viewport to match the size of the canvas's
    // drawingBuffer this will always be correct
    gl.viewport(0, 0, gl.drawingBufferWidth, gl.drawingBufferHeight);

    this.renderer = new THREE.WebGLRenderer({canvas});

    this.scene = new THREE.Scene();

    this.camera = new THREE.PerspectiveCamera(
      fov, canvas.clientWidth / canvas.clientHeight, near, far);
    this.camera.position.z = 20;

    let program = gl.getParameter(gl.CURRENT_PROGRAM) as number;
    this.addrProjectionMatrix = gl.getUniformLocation(program, "projectionMatrix")!;
    this.addrModelViewMatrix = gl.getUniformLocation(program, "modelViewMatrix")!;

    gl.uniformMatrix4fv(this.addrProjectionMatrix, false,
      this.camera.projectionMatrix.toArray());
    gl.uniformMatrix4fv(this.addrModelViewMatrix, false,
      this.camera.matrixWorld.toArray());


    this.control = new OrbitControls(this.camera, this.renderer.domElement);
    this.control.addEventListener('change', this.render.bind(this));
    this.render();
  }

  resize() {
    let gl = this.context.context;
    let width = gl.canvas.clientWidth;
    let height = gl.canvas.clientHeight;
    if (gl.canvas.width != width ||
        gl.canvas.height != height) {
      gl.canvas.width = width;
      gl.canvas.height = height;
    }
  }

  render() {
    let gl = this.context.context;
    this.resize();
    gl.viewport(0, 0, gl.canvas.width, gl.canvas.height);
    this.camera.updateMatrixWorld(false);
    this.camera.matrixWorldInverse.getInverse( this.camera.matrixWorld );
    gl.uniformMatrix4fv(this.addrModelViewMatrix, false,
      this.camera.matrixWorldInverse.toArray());
    if (this.renderCallback !== undefined) {
      this.renderCallback();
    }
  }

  protected context: Context;
  protected renderer: THREE.WebGLRenderer;
  protected scene: THREE.Scene;
  protected camera: THREE.Camera;
  protected control: OrbitControls;

  protected addrProjectionMatrix: WebGLUniformLocation;
  protected addrModelViewMatrix: WebGLUniformLocation;

  protected renderCallback?: () => void;
}
