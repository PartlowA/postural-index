import open3d as o3d
import open3d.visualization.gui as gui
import open3d.visualization.rendering as rendering
import numpy as np
import copy

from typing import List
from functools import partial

import random # testing visualiser

from measurement_manager import MeasurementManager
from cbm_measurement import CbmMeasurement
from registration import Registration

class PosturalIndexWindow():
    """
    """

    """
    """
    def __init__(self, window_title: str, width: int, height: int, measurement_manager: MeasurementManager) -> None:
        self._window = gui.Application.instance.create_window(window_title, width, height)
        self._measurement_manager = measurement_manager

        self._selected_measurement: str = None
        self._interpolation_iterations: int = 0
        self._show_wireframe_mesh: bool = False
        self._show_triangle_mesh: bool = True
        self._triangle_mesh: o3d.geometry.TriangleMesh = None
        self._wireframe_mesh: o3d.geometry.LineSet = None
        self._rigid_registration_result: o3d.geometry.TriangleMesh = None
        self._rigid_registration_result_wireframe: o3d.geometry.LineSet = None

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
        self._scene.look_at(
            np.array([0, 0, 0]),
            np.array([0.22676212, 0.48644078, 0.05129611]),
            np.array([0, 0, 1.0])
        )

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

        show_wireframe = gui.Checkbox("Show measurement wireframe?")
        show_wireframe.set_on_checked(self._on_show_wireframe_value_changed)
        measurement_collapsable.add_child(show_wireframe)
        measurement_collapsable.add_fixed(em)

        # Registration Section
        registration_collapsable = gui.CollapsableVert("Registration", 0.25 * em, gui.Margins(em, 0, 0, 0))
        
        reset_registration_button_row = gui.Horiz()
        reset_registration_button = gui.Button("Reset")
        reset_registration_button.set_on_clicked(self._on_reset_register)
        reset_registration_button_row.add_child(reset_registration_button)

        rigid_registration_options = gui.Combobox()
        rigid_registration_options.add_item("pycpd - rigid")
        rigid_registration_options.add_item("pycpd - affine")
        rigid_registration_combo = gui.Horiz()
        rigid_registration_combo.add_child(gui.Label("Step 1: "))
        rigid_registration_combo.add_fixed(em)
        rigid_registration_combo.add_child(rigid_registration_options)
        rigid_registration_button_row = gui.Horiz()
        rigid_registration_button = gui.Button("Register")
        rigid_registration_button.set_on_clicked(self._on_rigid_register)
        rigid_registration_button_row.add_child(rigid_registration_button)
                
        soft_registration_options = gui.Combobox()
        soft_registration_options.add_item("pycpd - deformable")
        soft_registration_combo = gui.Horiz()
        soft_registration_combo.add_child(gui.Label("Step 2: "))
        soft_registration_combo.add_fixed(em)
        soft_registration_combo.add_child(soft_registration_options)
        soft_registration_button_row = gui.Horiz()
        soft_registration_button = gui.Button("Register")
        soft_registration_button.set_on_clicked(self._on_soft_register)
        soft_registration_button_row.add_child(soft_registration_button)

        registration_collapsable.add_child(reset_registration_button_row)
        registration_collapsable.add_fixed(em)
        registration_collapsable.add_child(rigid_registration_combo)
        registration_collapsable.add_fixed(em)
        registration_collapsable.add_child(rigid_registration_button_row)
        registration_collapsable.add_fixed(em)
        registration_collapsable.add_child(soft_registration_combo)
        registration_collapsable.add_fixed(em)
        registration_collapsable.add_child(soft_registration_button_row)
        registration_collapsable.add_fixed(em)

        # Information Section
        information_collapsable = gui.CollapsableVert("System Information", 0.25 * em, gui.Margins(em, 0, 0, 0))
        camera_details = gui.Button("Capture Camera Position")
        camera_details.set_on_clicked(self._save_camera_details)
        information_collapsable.add_child(camera_details)

        # Add sections to side panel
        self._settings_panel.add_child(measurement_collapsable)
        self._settings_panel.add_child(registration_collapsable)
        self._settings_panel.add_child(information_collapsable)

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

        try:
            if self._rigid_registration_result is not None:
                mat = rendering.MaterialRecord()
                mat.shader = "defaultLit"
                mat.base_color = [random.random(), random.random(), random.random(), 1.0]
                self._add_model_to_scene(
                    "Rigid Registered",
                    self._rigid_registration_result,
                    mat
                )
        except Exception as e:
            print(e)

        try:
            if self._soft_registration_result is not None:
                mat = rendering.MaterialRecord()
                mat.shader = "defaultLit"
                mat.base_color = [random.random(), random.random(), random.random(), 1.0]
                self._add_model_to_scene(
                    "Soft Registered",
                    self._soft_registration_result,
                    mat
                )
        except Exception as e:
            print(e)  
            
    def _add_model_to_scene(self, name: str, model, material: rendering.MaterialRecord):
        if model == None:
            return
                
        self._scene.scene.add_geometry(name, model, material)

    def _save_camera_details(self) -> None:
        print(self._scene.center_of_rotation)

    def _on_reset_register(self) -> None:
        print("Reset position")

    def _on_rigid_register(self) -> None:
        X = self._normal_triangle_mesh
        Y = self._triangle_mesh
        #self._rigid_registration_result = copy.deepcopy(self._triangle_mesh)
        #self._add_geometry_to_scene()
        #callback = partial(register_callback, scene = self._scene, model_name = "Rigid Registered", source = self._triangle_mesh, window = self._window)
        # self._rigid_registration_result = Registration.register([X, Y], "affine", callback)[1]
        self._rigid_registration_result = Registration.register([X, Y], "affine")[1]
        self._add_geometry_to_scene()
        print("Rigid registration complete")

    def _on_soft_register(self) -> None:
        
        try:
            X = self._normal_triangle_mesh
            Y = self._rigid_registration_result
            self._soft_registration_result = Registration.register([X, Y], "soft")[1]
            self._add_geometry_to_scene()
        except Exception as e:
            print(e)  
        print("Soft registration complete")

def register_callback(iteration, error, X, Y, scene: rendering.Scene, model_name, source, window) -> None:
    try:
        print(f"Frame: {iteration}, error: {error}.")
        registered = copy.deepcopy(source)
        registered.vertices = o3d.utility.Vector3dVector(Y)
        scene.scene.remove_geometry(model_name)
        mat = rendering.MaterialRecord()
        mat.shader = "defaultLit"
        mat.base_color = [0.0, 1.0, 0.0, 1.0]
        scene.scene.add_geometry(
            "Rigid Registered",
            registered,
            mat
        )
        scene.force_redraw()
        window.post_redraw()
    except Exception as e:
        print(e)

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

    # Process all measurements and output graph

if __name__ == "__main__":
    main()