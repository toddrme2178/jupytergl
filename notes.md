
# Notes about exposing WebGL interface over Jupyter server

## WebGL interface

Should expose the methods and constants on the context. Clients can decide to declare constants from spec, or expose constants as queried from the javascript side. A list of methods available should be queryable. Calls to non-existant methods should either:

- Simply be discarded silently (and the rest performed).
- Halt execution and signal an invalid instruction.
- Be discarded and signal an invalid instruction (but still perform other instructions).
- Have a configuration to select among the above behaviors.


There are certain aspects of the WebGL interface that does not translate directly:

- gl.viewport -> Set the rendering resolution without CSS. Sometimes you want this done as a function of the size of the actual canvas element (with css). A function to call `gl.viewport(0, 0, canvas.width, canvas.height);` should therefore be exposed.
- Sending buffers might need an optimized transfer method.
- An interface for remotely manipulating buffers into javascript arrays should be considered.
- Client code will need to abstract away glBegin/glEnd calls.
- Loop: We should maybe supply a basic message loop (rotate/translate/zoom). Anything more complex we will somehow need to input


The only things that make sense to use this for are:

- Setup a static scene with interactive inspection (camera view).
- Setup a view where the kernel pushes scene instructions per frame (chunk).
- Setup a view which updates the scene once it receives instructions for a new/updated scene (chunk).

For thight couplings client data <--> interaction loop, this will likely not work very well, as the idea is based on not storing any data/state on javascript side.


### Operations

To minimze chatter, it will maybe make sense to bundle some calls together in one chunk, e.g. for initialization code. This will need to be handled on the client side, but at least there should be support on the server side to receive an array of instructions.


### Access to static content in the DOM

Access to shaders (and maybe geometry) stored in the DOM should be specced, where it can be identified by its element ID.


### Interface

Simple query/exec interface, where query returns the value from all / the last call(s).



## Program flow

### Static output (no kernel)

An output should contain: Buffers + shaders + WebGL instructions. This can be stored when live.

### Widget (kernel)

Kernel -> Javascript : instructions
[Kernel -> Javascript : buffers]
[Kernel -> Javascript : further init]
[Javascript -> Kernel : request instructions]
    [Kernel -> Javascript : buffers]
    [Kernel -> Javascript : instructions]

