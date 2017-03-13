# ----------------------------------------------------------------------------
# PyWavefront
# Copyright (c) 2013 Kurt Yoder
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#  * Neither the name of PyWavefront nor the names of its
#    contributors may be used to endorse or promote products
#    derived from this software without specific prior written
#    permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
# ----------------------------------------------------------------------------

import os
from functools import partial

from collections import namedtuple

import numpy as np

InterleavedIndices = namedtuple(
    'InterleavedIndices', ('v', 'n', 't'))

Face = namedtuple(
    'Face', ('vertex_indices', 'normal_indices', 'tex_coord_indices'))


def load_obj(filename):
    internal = Wavefront(filename)
    return [create_mesh(internal, mesh) for mesh in internal.mesh_list]


class PywavefrontException(Exception):
    pass


class Parser:
    """This defines a generalized parse dispatcher; all parse functions
    reside in subclasses."""

    def read_file(self, file_name):
        for line in open(file_name, 'r'):
            self.parse(line, dir=os.path.dirname(file_name))

    def parse(self, line, dir):
        """Determine what type of line we are and dispatch
        appropriately."""
        if line.startswith('#'):
            return

        values = line.split()
        if len(values) < 2:
            return

        line_type = values[0]
        args = values[1:]
        i = 0
        for arg in args:
            if dir != '' and ('mtllib' in line or 'map_Kd' in line):
                args[i] = dir + '/' + arg
            else:
                args[i] = arg
            i += 1

        parse_function = getattr(self, 'parse_%s' % line_type)
        parse_function(args)


class Wavefront:
    """Import a wavefront .obj file."""
    def __init__(self, file_name):
        self.file_name = file_name

        self.vertices = [[0., 0., 0.]]
        self.normals = [[0., 0., 0.]]
        self.tex_coords = [[0., 0.]]
        self.colors = [(0, 0, 0)]
        self.materials = {}
        self.meshes = {}        # Name mapping
        self.mesh_list = []     # Also includes anonymous meshes

        ObjParser(self, self.file_name)

    def add_mesh(self, the_mesh):
        self.mesh_list.append(the_mesh)
        if not the_mesh.name:
            return
        self.meshes[the_mesh.name] = the_mesh


class ObjParser(Parser):
    """This parser parses lines from .obj files."""
    def __init__(self, wavefront, file_name):
        # unfortunately we can't escape from external effects on the
        # wavefront object
        self.wavefront = wavefront
        self.mesh = None
        self.material = None
        # Use to duplicate vertices with uncommon normal_index/texture index
        self.index_lut = None

        self.read_file(file_name)

    # methods for parsing types of wavefront lines
    def parse_v(self, args):
        self.wavefront.vertices.append(list(map(float, args[0:3])))

    def parse_vn(self, args):
        self.wavefront.normals.append(list(map(float, args[0:3])))

    def parse_vt(self, args):
        self.wavefront.tex_coords.append(list(map(float, args[0:2])))

    def parse_mtllib(self, args):
        [mtllib] = args
        materials = MaterialParser(mtllib).materials
        for material_name, material_object in materials.items():
            self.wavefront.materials[material_name] = material_object

    def parse_usemtl(self, args):
        [usemtl] = args
        self.material = self.wavefront.materials.get(usemtl, None)
        if self.material is None:
            raise PywavefrontException('Unknown material: %s' % args[0])
        if self.mesh is not None:
            self.mesh.add_material(self.material)

    def parse_usemat(self, args):
        self.parse_usemtl(args)

    def parse_o(self, args):
        [o] = args
        self.mesh = InternalMesh(o)
        self.wavefront.add_mesh(self.mesh)

    def parse_g(self, args):
        pass

    def parse_f(self, args):
        if self.mesh is None:
            self.mesh = InternalMesh()
            self.wavefront.add_mesh(self.mesh)
        if self.material is None:
            self.material = Material()
        self.mesh.add_material(self.material)

        if self.index_lut is None and (self.wavefront.normals or self.wavefront.tex_coords):
            # Need to assure each index triplet is unique
            self.index_lut = {i: {} for i in range(len(self.wavefront.vertices))}

        # For fan triangulation, remember first and latest vertices
        first_indices = None
        previous_indices = None
        for i, v in enumerate(args[0:]):
            if type(v) is bytes:
                v = v.decode()
            v_index, t_index, n_index = \
                (list(map(int, [j or 0 for j in v.split('/')])) + [0, 0])[:3]
            if v_index < 0:
                v_index += len(self.wavefront.vertices) - 1
            if t_index < 0:
                t_index += len(self.wavefront.tex_coords) - 1
            if n_index < 0:
                n_index += len(self.wavefront.normals) - 1

            indices = InterleavedIndices(v_index, n_index, t_index)

            if i >= 2:
                # Triangulate
                self.mesh.faces.append(Face(
                    (first_indices.v, previous_indices.v, indices.v),
                    (first_indices.n, previous_indices.n, indices.n),
                    (first_indices.t, previous_indices.t, indices.t),
                ))
            elif i == 0:
                first_indices = indices
            previous_indices = indices

    def parse_s(self, args):
        # unimplemented
        return


class MaterialParser(Parser):
    """Object to parse lines of a materials definition file."""

    def __init__(self, file_path):
        self.materials = {}
        self.this_material = None
        self.read_file(file_path)

    def parse_newmtl(self, args):
        [newmtl] = args
        self.this_material = Material(newmtl)
        self.materials[self.this_material.name] = self.this_material

    def parse_Kd(self, args):
        self.this_material.set_diffuse(args)

    def parse_Ka(self, args):
        self.this_material.set_ambient(args)

    def parse_Ks(self, args):
        self.this_material.set_specular(args)

    def parse_Ke(self, args):
        self.this_material.set_emissive(args)

    def parse_Ns(self, args):
        [Ns] = args
        self.this_material.shininess = float(Ns)

    def parse_d(self, args):
        [d] = args
        self.this_material.set_alpha(d)

    def __getattr__(self, name):
        if name.startswith('parse_map_'):
            return partial(self.parse_map, name[len('parse_map_'):])
        else:
            raise AttributeError(name)

    def parse_map(self, name, args):
        self.this_material.add_texture(name, args[-1])

    def parse_Ni(self, args):
        # unimplemented
        return

    def parse_illum(self, args):
        # unimplemented
        return


class Material:
    def __init__(self, name):
        self.name = name
        self.diffuse = [.8, .8, .8, 1.]
        self.ambient = [.2, .2, .2, 1.]
        self.specular = [0., 0., 0., 1.]
        self.emissive = [0., 0., 0., 1.]
        self.shininess = 0.
        self.textures = {}

    @property
    def normals(self):
        if self._normals:
            return self._normals
        # TODO: Compute from geometry
        return self._normals

    def pad_light(self, values):
        """Accept an array of up to 4 values, and return an array of 4 values.
        If the input array is less than length 4, pad it with zeroes until it
        is length 4. Also ensure each value is a float"""
        while len(values) < 4:
            values.append(0.)
        return list(map(float, values))

    def set_alpha(self, alpha):
        """Set alpha/last value on all four lighting attributes."""
        alpha = float(alpha)
        self.diffuse[3] = alpha
        self.ambient[3] = alpha
        self.specular[3] = alpha
        self.emissive[3] = alpha

    def set_diffuse(self, values=[]):
        self.diffuse = self.pad_light(values)

    def set_ambient(self, values=[]):
        self.ambient = self.pad_light(values)

    def set_specular(self, values=[]):
        self.specular = self.pad_light(values)

    def set_emissive(self, values=[]):
        self.emissive = self.pad_light(values)

    def add_texture(self, kind, path):
        self.textures[kind] = Texture(path)


class InternalMesh:
    """This is a basic mesh for drawing using OpenGL."""

    def __init__(self, name=''):
        self.name = name
        self.materials = []
        self.faces = []

    def has_material(self, new_material):
        """Determine whether we already have a material of this name."""
        for material in self.materials:
            if material.name == new_material.name:
                return True
        return False

    def add_material(self, material):
        """Add a material to the mesh, IFF it is not already present."""
        if self.has_material(material):
            return
        self.materials.append(material)


class Texture:
    def __init__(self, path):
        from PIL import Image
        self.image_name = path
        self.image = np.array(Image.open(self.image_name), dtype=np.uint8)


class Mesh:
    def __init__(self, name, n_faces, materials):
        self.name = name
        self.vertices = []
        self.normals = []
        self.texture_coords = []

        unknown_id = 0
        self.materials = {}
        for m in materials:
            name = m.name
            if not name:
                name = 'unknown_material_%s' % unknown_id
                unknown_id += 1
            self.materials[name] = m

        self.faces = np.empty((n_faces, 3), np.uint16)


def create_mesh(model, source_mesh):
    mesh = Mesh(source_mesh.name, len(source_mesh.faces), source_mesh.materials)

    # Copy vertices, normals and textures into Mesh instance
    indices_seen = {}
    for face_out_index, source_face in enumerate(source_mesh.faces):
        # Copy all index arrays
        for i, composit_index in enumerate(zip(source_face.vertex_indices,
                                               source_face.normal_indices,
                                               source_face.tex_coord_indices)):
            try:
                new_index = indices_seen[composit_index]
            except KeyError:
                new_index = len(mesh.vertices)
                indices_seen[composit_index] = new_index
                (vi, ni, ti) = composit_index
                mesh.vertices.append(model.vertices[vi])
                mesh.normals.append(model.normals[ni])
                mesh.texture_coords.append(model.tex_coords[ti])

            # Set destination face indices:
            mesh.faces[face_out_index, i] = new_index
    mesh.vertices = np.array(mesh.vertices, np.float32)
    mesh.normals = np.array(mesh.normals, np.float32) if mesh.normals else None
    mesh.texture_coords = np.array(mesh.texture_coords, np.float32) if mesh.texture_coords else None
    return mesh
