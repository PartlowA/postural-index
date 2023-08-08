import open3d as o3d
import open3d.visualization.gui as gui
import open3d.visualization.rendering as rendering

from typing import List

import random # testing visualiser

from measurement_manager import MeasurementManager
from cbm_measurement import CbmMeasurement
from registration import Registration

class PosturalIndexWindow():
    """
    """

    """"""
    def __init__(self, window_title: str, width: int, height: int, measurement_manager: MeasurementManager) -> None:
        self._window = gui.Application.instance.create_window(window_title, width, height)
        self._measurement_manager = measurement_manager

        self._selected_measurement: str = None
        self._interpolation_iterations: int = 0
        self._show_wireframe_mesh: bool = False
        self._show_triangle_mesh: bool = True
        self._triangle_mesh: o3d.geometry.TriangleMesh = None
        self._wireframe_mesh: o3d.geometry.LineSet = None

        # Create the normal measurement
        control_measurements = measurement_manager.get_normal_measurements()
        self._control_mesh_names = [m.name for m in control_measurements]
        self._control_triangle_meshes = [load_triangle_mesh(m) for m in control_measurements]
        self._control_wireframe_meshes = [load_wireframe_mesh(m) for m in self._control_triangle_meshes]
        registered_controls = Registration.register(self._control_triangle_meshes, "affine")
        self._normal_triangle_mesh = o3d.geometry.TriangleMesh = Registration.calculate_average_mesh(registered_controls)
        self._normal_wireframe_mesh = o3d.geometry.LineSet = load_wireframe_mesh(self._normal_triangle_mesh)
        
        # Setup GUI
        self._scene = gui.SceneWidget()
        self._scene.scene = rendering.Open3DScene(self._window.renderer)

        em = self._window.theme.font_size
        self._settings_panel = gui.Vert(0, gui.Margins(0.25 * em, 0.25 * em, 0.25 * em, 0.25 * em))

        # A section where you can select which measurement to visualise
        measurement_collapsable = gui.CollapsableVert("Measurement", 0.25 * em, gui.Margins(em, 0, 0, 0))
        measurement_collapsable.add_child(gui.Label("Select a measurement"))
        
        # A list of measurements
        measurement_list_view = gui.ListView()
        measurement_list_view.set_items(self._measurement_manager.get_measurement_names())
        # measurement_list_view.selected_index = measurement_list_view.selected_index + 1  # initially is -1, so now 1
        measurement_list_view.set_max_visible_items(10)
        measurement_list_view.set_on_selection_changed(self._on_select_measurement)
        measurement_collapsable.add_child(measurement_list_view)

        # Interpolation iterations
        interpolation_nedit = gui.NumberEdit(gui.NumberEdit.INT)
        interpolation_nedit.int_value = self._interpolation_iterations
        interpolation_nedit.set_limits(0, 5)  # value coerced to 1
        interpolation_nedit.set_on_value_changed(self._on_interpolation_value_changed)
        interpolation_layout = gui.Horiz()
        interpolation_layout.add_child(gui.Label("Interpolation iterations:"))
        interpolation_layout.add_fixed(em)
        interpolation_layout.add_child(interpolation_nedit)
        measurement_collapsable.add_child(interpolation_layout)

        show_wireframe = gui.Checkbox("Show wireframe?")
        show_wireframe.set_on_checked(self._on_show_wireframe_value_changed)
        measurement_collapsable.add_child(show_wireframe)

        # Add section to side panel
        self._settings_panel.add_child(measurement_collapsable)

        # Setup the panel on the right hand side and the scene on the left
        self._window.set_on_layout(self._on_layout)
        self._window.add_child(self._scene)
        self._window.add_child(self._settings_panel)


    # Callback to set the layout of the windows direct children
    # See: http://www.open3d.org/docs/release/python_example/visualization/index.html#vis-gui-py
    def _on_layout(self, layout_context):
        r = self._window.content_rect
        self._scene.frame = r
        width = 20 * layout_context.theme.font_size
        height = min(r.height, self._settings_panel.calc_preferred_size(layout_context, gui.Widget.Constraints()).height)
        self._settings_panel.frame = gui.Rect(r.get_right() - width, r.y, width, height)


    def _on_show_wireframe_value_changed(self, is_checked):
        self._show_wireframe_mesh = is_checked
        self._scene.scene.show_geometry(f"{self._selected_measurement}-wireframe", is_checked)


    def _on_interpolation_value_changed(self, new_val):
        self._interpolation_iterations = int(new_val)
        self._load_cbm_measurement()
        self._add_geometry_to_scene()


    def _on_select_measurement(self, new_val: str, _: bool) -> None:
        if self._selected_measurement == new_val:
            return
        
        self._selected_measurement = new_val
        self._load_cbm_measurement()
        self._add_geometry_to_scene()


    def _load_cbm_measurement(self):
        cbm_measurement = self._measurement_manager.create_cbm_measurement(self._selected_measurement)
        self._triangle_mesh = load_triangle_mesh(cbm_measurement, self._interpolation_iterations)
        self._wireframe_mesh = load_wireframe_mesh(self._triangle_mesh)


    def _add_geometry_to_scene(self) -> None:
        self._scene.scene.clear_geometry()

        if self._show_triangle_mesh:
            mat = rendering.MaterialRecord()
            mat.shader = "defaultLit"
            mat.base_color = [random.random(), random.random(), random.random(), 1.0]
            self._add_model_to_scene(
                f"{self._selected_measurement}-mesh",
                self._triangle_mesh,
                mat
            )

        mat = rendering.MaterialRecord()
        mat.shader = "unlitLine"
        mat.line_width = 2
        mat.base_color = [1.0, 1.0, 1.0, 1.0]
        mat.emissive_color = [1.0, 1.0, 1.0, 1.0]
        self._add_model_to_scene(
            f"{self._selected_measurement}-wireframe",
            self._wireframe_mesh,
            mat
        )

        mat = rendering.MaterialRecord()
        mat.shader = "defaultLit"
        mat.line_width = 2
        mat.base_color = [1.0, 0.0, 0.0, 1.0]
        self._add_model_to_scene(
            "Normal",
            self._normal_triangle_mesh,
            mat
        )
        

    
    def _add_model_to_scene(self, name: str, model, material: rendering.MaterialRecord):
        if model == None:
            return
                
        self._scene.scene.add_geometry(name, model, material)

def load_triangle_mesh(cbm_measurement: CbmMeasurement, interpolation_iterations: int = 0) -> None:
    mesh = o3d.t.geometry.TriangleMesh(cbm_measurement.V, cbm_measurement.T)
    mesh.triangle.normals = cbm_measurement.N
    mesh.compute_vertex_normals()
    mesh.normalize_normals()
    mesh = mesh.to_legacy()
    mesh = mesh.subdivide_loop(number_of_iterations = interpolation_iterations)
    return mesh
    
def load_wireframe_mesh(triangle_mesh) -> None:
    wireframe_mesh = o3d.geometry.LineSet.create_from_triangle_mesh(triangle_mesh)  
    return wireframe_mesh



def main():
    # Setup the measurement specific stuff
    root_folder = "C:\source\Postural Index\CBM Data"
    measurement_manager = MeasurementManager()

    # Initialise the application
    o3d.utility.set_verbosity_level(o3d.utility.VerbosityLevel.Debug)
    gui.Application.instance.initialize()

    # Setup the window
    window = PosturalIndexWindow("Postural Index", 1920, 1080, measurement_manager)

    # Run event loop
    gui.Application.instance.run()

if __name__ == "__main__":
    main()