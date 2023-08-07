import open3d.visualization.gui as gui
import open3d.visualization.rendering as rendering

from measurement_manager import MeasurementManager

class PosturalIndexWindow():
    def __init__(self, window_title: str, width: int, height: int, measurement_manager: MeasurementManager) -> None:
        self._window = gui.Application.instance.create_window(window_title, width, height)
        self._measurement_manager = measurement_manager

        w = self._window

        self._scene = gui.SceneWidget()
        self._scene.scene = rendering.Open3DScene(w.renderer)

        em = w.theme.font_size
        self._settings_panel = gui.Vert(0, gui.Margins(0.25 * em, 0.25 * em, 0.25 * em, 0.25 * em))

        # A section where you can select which measurement to visualise
        measurement_collapsable = gui.CollapsableVert("Measurement", 0.25 * em, gui.Margins(em, 0, 0, 0))
        measurement_collapsable.add_child(gui.Label("Select a measurement"))
        
        # A list of measurements
        measurement_list_view = gui.ListView()
        measurement_list_view.set_items(self._measurement_manager.get_measurement_names())
        measurement_list_view.selected_index = measurement_list_view.selected_index + 1  # initially is -1, so now 1
        measurement_list_view.set_max_visible_items(10)
        measurement_list_view.set_on_selection_changed(self._on_select_measurement)
        measurement_collapsable.add_child(measurement_list_view)

        # Add section to side panel
        self._settings_panel.add_child(measurement_collapsable)

        # Setup the panel on the right hand side and the scene on the left
        w.set_on_layout(self._on_layout)
        w.add_child(self._scene)
        w.add_child(self._settings_panel)


    # Callback to set the layout of the windows direct children
    # See: http://www.open3d.org/docs/release/python_example/visualization/index.html#vis-gui-py
    def _on_layout(self, layout_context):
        r = self._window.content_rect
        self._scene.frame = r
        width = 17 * layout_context.theme.font_size
        height = min(r.height, self._settings_panel.calc_preferred_size(layout_context, gui.Widget.Constraints()).height)
        self._settings_panel.frame = gui.Rect(r.get_right() - width, r.y, width, height)


    def _on_select_measurement(self):
        pass

def main():
    # Setup the measurement specific stuff
    root_folder = "C:\source\Postural Index\CBM Data"
    measurement_manager = MeasurementManager()

    # Initialise the application
    gui.Application.instance.initialize()

    # Setup the window
    window = PosturalIndexWindow("Postural Index", 1920, 1080, measurement_manager)

    # Run event loop
    gui.Application.instance.run()

if __name__ == "__main__":
    main()