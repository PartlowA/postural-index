"""Contains the MeasurementManager class which is used for importing Cardiff Contoured Cushions from different sources.

Currently implemented sources only include Cardiff Body Match (CBM) DG2 files.

Typical usage example:
    measurement_manager = MeasurementManager("C:\measurements")
    control_measurements = measurement_manager.get_cbm_measurements(type = "control")
"""
import numpy as np
import pandas as pd
import os
import pathlib

from typing import List

from cbm_measurement import CbmMeasurement

class MeasurementManager:
    """Imports Cardiff Contoured Cushion shapes from various sources.

    The measurement manager is initialised with a root folder.
    The root folder may contain subfolders which may or may not contain measurements.
    The measurement manager currently only identifies files with a .DG2 extension.
    The measurement manager does not validate the structure of the DG2 file and assumees they are correct.

    Attributes:
        root:
            A string value containing the folder where measurements are stored.
    """


    def __init__(self) -> None:
        """Initialises the instance and sets the root.
        It will attempt to set the root to a directory called data.
        If the environment variable is not found and data doesn't exist an exception is raised.
        
        Args:
            root_folder:
                The folder containing measurements. It may contain subfolders.

        Raises:
            LookupError:
                If the environment variables DG2_ROOT or the data folder cannot be located.
            LookupError:
                If the file trial_data.csv cannot be located
        """
        try:
            root_folder = os.environ['DG2_ROOT']
            root_folder = pathlib.Path(root_folder)
        except:
            data_exists = pathlib.Path("data").exists()
            if not data_exists:
                raise LookupError(f"Unable to locate environment variable VAR or a data folder.")
            else:
                current_directory = pathlib.Path().resolve()
                root_folder = current_directory.joinpath("data")
                
        self._root = root_folder

        data_path = self._root.joinpath("trial-data.csv")
        self._measurement_details = pd.read_csv(
            data_path, 
            usecols = [
                "participant",
                "base",
                "back",
                "angle",
                "pointer",
                "posture",
                "control"
            ],
            dtype={
                "participant": str,
                "base": str,
                "back": str,
                "angle": float,
                "pointer": float,
                "posture": str,
                "control": bool
        })

  
    def create_cbm_measurement(self, participant: str, posture: str = ""):
        if posture == "":
            record = self._measurement_details.query("participant == @participant").iloc[0]
        else:
            record = self._measurement_details.query("participant == @participant and posture == @posture").iloc[0]

        back, back_info = self.get_dg2_as_matrix(record["back"])
        base, base_info = self.get_dg2_as_matrix(record["base"])

        cbm_measurement = CbmMeasurement(participant, base, back, record["pointer"], record["angle"])

        return cbm_measurement
    
    def get_normal_measurements(self) -> List[CbmMeasurement]:
        records = self._measurement_details.query("control == True")
        cbm_measurements = [self.create_cbm_measurement(row["participant"]) for _, row in records.iterrows()]
        return cbm_measurements

    def get_dg2_as_matrix(self, dg2_file):
        """Reads a DG2 file and returns the measurement component as a 10x10 element numpy array.

        Args:
            dg2_file:
                the id of the DG2 file.

        Returns:
            matrix:
                An 2d np.array containing the values from the DG2 measurement.
            info:
                A dictionary containing information about the DG2 measurement.  
        """
        
        vector, info = self.get_dg2_as_vector(dg2_file)
        rn = info["number of rows"]
        cn = info["number of columns"]

        # Orient the matrix so that the front (for bases) or bottom (for backs) of the measurement is on the bottom row
        matrix_reshaped = np.reshape(vector, [rn, cn])
        matrix = np.flip(matrix_reshaped, axis = 1)

        return matrix, info
    

    def get_dg2_as_vector(self, dg2_file):
        """Reads a DG2 file and returns the measurement component as a 100 element numpy array.

        Args:
            dg2_file:
                the id of the DG2 file.

        Returns:
            vector:
                An array containing the values from the DG2 measurement.
            info:
                A dictionary containing information about the DG2 measurement.                

        """
        dg2_file = self.get_measurement_file_path(dg2_file)
        contents = np.loadtxt(dg2_file, dtype = str)
        data_form = int(contents[1].partition("=")[2])
        machine_number = int(contents[2].partition("=")[2])
        date_digitised = contents[3].partition("=")[2]
        pointer_position = int(contents[4].partition("=")[2])
        row_resolution = contents[9].astype(float)
        column_resolution = contents[10].astype(float)
        number_of_rows = contents[11].astype(int)
        number_of_columns = contents[12].astype(int)
        number_of_elements = number_of_rows * number_of_columns
        array = contents[-number_of_elements:].astype(float) # only select the last rn x cn lines which are the measurement
        
        array = array / 1000 # convert to metres
        row_resolution = row_resolution / 1000
        column_resolution = column_resolution / 1000

        info = {
            "data sheet": data_form,
            "cbm mechanical shape sensor": machine_number,
            "date digitised": date_digitised,
            "pointer position": pointer_position,
            "number of rows": number_of_rows,
            "number of columns": number_of_columns,
            "row resolution": row_resolution,
            "column resolution": column_resolution
        }

        return array, info
    

    def get_measurement_file_path(self, id: str) -> str:
        dg2_file = ""
        for file in self._root.glob(f"**/*{id}*.DG2"):
            # for filename in files:
            # name, extension = os.path.splitext(filename)
            if (file.stem == id):
                dg2_file = file
                break
        return dg2_file
    
    def get_measurement_names(self) -> pd.DataFrame:
        """Returns a list of measurement names from the measurement_details object.

        Args:
            None.

        Returns:
            names:
                A list containing all the participant names.
        """
        return self._measurement_details.filter(["participant", "posture", "control"])
    
    
    def _create_normal_measurement(self, measurements: List[CbmMeasurement]):
        """Returns a statistical average mesh from the control measurements.
        
        Args:
            measurements:
                A list of o3d.geometry.TriangleMesh objects. The first element will be the basis for the construction of the average shape.
        """

        if len(measurements) == 0:
            print("There are no control measurements.")
            return
        
        V = np.asarray(measurements[0].vertices)
        T = np.asarray(measurements[0].triangles)

        if len(measurements) == 1:
            return V, T
        

        # Get all the measurements except the first one as point clouds
        meshes = [np.asarray(M.vertices) for M in measurements[1:]]

        def get_nearest_displacement_vectors(X, Y):
            vectors = []
            for v in X:
                d = np.linalg.norm(v - Y, axis = 1)
                idx = d.argmin()
                vector = Y[idx] - v
                vectors.append(vector)
            return vectors           

        # Calculate the dispacement vector to the nearest point in each of the meshes
        displacement_vectors = [get_nearest_displacement_vectors(V, M) for M in meshes]

        # For each point in A calculate the average distance to the nearest point
        average_displacement_vectors = np.mean(displacement_vectors, axis = 0)

        # Calculate the dispacements for the nearest point in each of the meshes
        magnitudes = np.linalg.norm(average_displacement_vectors, axis = 1)

#     # Reference for plot    
#     reference = o3d.t.geometry.TriangleMesh(V, T)
#     reference = reference.to_legacy()

        # Construct the average mesh
        TV = V + average_displacement_vectors
        # average_mesh = o3d.t.geometry.TriangleMesh(TV, T)
        # norm = mpl.colors.Normalize(np.min(magnitudes), np.max(magnitudes))
        # cmap = cm.GnBu
        # m = cm.ScalarMappable(norm = norm, cmap = cmap)
        # colours = m.to_rgba(magnitudes)
        # colours = colours[:, 0:3]
        # average_mesh.vertex.colors = colours
        # average_mesh = average_mesh.to_legacy()

#     if plot_result:
#         fig = go.Figure()
#         add_mesh_to_figure(fig, "Reference Image", reference)
#         add_mesh_to_figure(fig, "Average Mesh", average_mesh)
#         camera = dict(up=dict(x=0, y=0, z=1),center=dict(x=0, y=0, z=0),eye=dict(x=1.5, y=-1.5, z=1.5))
#         fig.update_layout(scene_camera = camera)
#         fig.show()

        return TV, T
    

def main():
    # Example usage
    mm = MeasurementManager()

    m = mm.get_measurement_file_path("Arrow (Back)")
    print(m)

    cbm = mm.create_cbm_measurement("T001")
    print(cbm)


if __name__ == "__main__":
    main()