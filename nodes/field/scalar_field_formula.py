
import numpy as np

import bpy
from bpy.props import FloatProperty, EnumProperty, BoolProperty, IntProperty, StringProperty

from sverchok.node_tree import SverchCustomTreeNode, throttled
from sverchok.data_structure import updateNode, zip_long_repeat, fullList, match_long_repeat
from sverchok.utils.modules.eval_formula import get_variables, sv_compile, safe_eval_compiled
from sverchok.utils.logging import info, exception
from sverchok.utils.math import from_cylindrical, from_spherical, to_cylindrical, to_spherical

from sverchok_extra.data import coordinate_modes, SvExScalarFieldLambda

class SvExScalarFieldFormulaNode(bpy.types.Node, SverchCustomTreeNode):
    """
    Triggers: Scalar Field Formula
    Tooltip: Generate scalar field by formula
    """
    bl_idname = 'SvExScalarFieldFormulaNode'
    bl_label = 'Scalar Field'
    bl_icon = 'OUTLINER_OB_EMPTY'
    sv_icon = 'SV_VORONOI'

    formula: StringProperty(
            name = "Formula",
            default = "x*x + y*y + z*z",
            update = updateNode)

    input_mode : EnumProperty(
        name = "Coordinates",
        items = coordinate_modes,
        default = 'XYZ',
        update = updateNode)

    def sv_init(self, context):
        self.outputs.new('SvExScalarFieldSocket', "Field").display_shape = 'CIRCLE_DOT'

    def draw_buttons(self, context, layout):
        layout.label(text="Input:")
        layout.prop(self, "input_mode", expand=True)
        layout.prop(self, "formula", text="")

    def make_function(self, variables):
        compiled = sv_compile(self.formula)

        def carthesian(x, y, z):
            variables.update(dict(x=x, y=y, z=z))
            return safe_eval_compiled(compiled, variables)

        def cylindrical(x, y, z):
            rho, phi, z = to_cylindrical((x, y, z), mode='radians')
            variables.update(dict(rho=rho, phi=phi, z=z))
            return safe_eval_compiled(compiled, variables)

        def spherical(x, y, z):
            rho, phi, theta = to_spherical((x, y, z), mode='radians')
            variables.update(dict(rho=rho, phi=phi, theta=theta))
            return safe_eval_compiled(compiled, variables)

        if self.input_mode == 'XYZ':
            function = carthesian
        elif self.input_mode == 'CYL':
            function = cylindrical
        else: # SPH
            function = spherical

        return function

    def get_coordinate_variables(self):
        if self.input_mode == 'XYZ':
            return {'x', 'y', 'z'}
        elif self.input_mode == 'CYL':
            return {'rho', 'phi', 'z'}
        else: # SPH
            return {'rho', 'phi', 'theta'}

    def get_variables(self):
        variables = get_variables(self.formula)
        variables.difference_update(self.get_coordinate_variables())
        return list(sorted(list(variables)))

    def adjust_sockets(self):
        variables = self.get_variables()
        for key in self.inputs.keys():
            if key not in variables:
                self.debug("Input {} not in variables {}, remove it".format(key, str(variables)))
                self.inputs.remove(self.inputs[key])
        for v in variables:
            if v not in self.inputs:
                self.debug("Variable {} not in inputs {}, add it".format(v, str(self.inputs.keys())))
                self.inputs.new('SvStringsSocket', v)

    def update(self):
        if not self.formula:
            return
        self.adjust_sockets()

    def get_input(self):
        variables = self.get_variables()
        inputs = {}

        for var in variables:
            if var in self.inputs and self.inputs[var].is_linked:
                inputs[var] = self.inputs[var].sv_get()
        return inputs

    def process(self):
        if not any(socket.is_linked for socket in self.outputs):
            return
        var_names = self.get_variables()
        inputs = self.get_input()
        input_values = [inputs.get(name, [[0]]) for name in var_names]
        if var_names:
            parameters = match_long_repeat(input_values)
        else:
            parameters = [[[]]]

        fields_out = []
        for objects in zip(*parameters):
            for var_values in zip_long_repeat(*objects):
                variables = dict(zip(var_names, var_values))
                function = self.make_function(variables.copy())
                field = SvExScalarFieldLambda(function, variables)
                fields_out.append(field)

        self.outputs['Field'].sv_set(fields_out)

def register():
    bpy.utils.register_class(SvExScalarFieldFormulaNode)

def unregister():
    bpy.utils.unregister_class(SvExScalarFieldFormulaNode)

