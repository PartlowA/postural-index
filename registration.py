import open3d as o3d
import numpy as np
import copy
import matplotlib as mpl
import matplotlib.cm as cm

from typing import List

# from pycpd import RigidRegistration
from pycpd import AffineRegistration
from pycpd import DeformableRegistration

class Registration():
    @staticmethod
    def register(measurements: List[o3d.geometry.TriangleMesh], method: str, callback = None) -> List[o3d.geometry.TriangleMesh]:
        """Registers a series of point clouds.

        The first measurement is used as the imovable point cloud.
        All other measurements are registered onto this point cloud.

        Args:
            measurements:
                A list of CbmMeasurement objects.
            method:
                The type of registration to perform. Accepted values are 'affine'.

        Returns:
            registered:
                A List of triangle mesh objects which have been registered with the mesh in the first element.
            information:
                A dictionary of parameters resulting from the transformation.
                For soft body registrations this is a List (of length len(registered)-1) of vectors representing the soft body registration.

        Raises:
            TypeError:
                If an element of measurements is of the incorrect type.
            NameError:
                If the specified method does not exist.
        """

        if len(measurements) == 0:
            print("You need to supply a list of CBM measurements to be registered.")
            return

        if len(measurements) == 1:
            return measurements[0]
        
        X = measurements[0]
        registered = []
        magnitudes = []
        registered.append(X)
    
        # Attempt to register each mesh
        for i in range(1, len(measurements)):
            Y = measurements[i]
            if method == "affine":
                TY = Registration.affine_registration(X, Y, callback)
            elif method == "soft":
                TY = Registration.soft_registration(X, Y)
            else:
                raise NameError(f"{method} is not a valid registration type.")
            # TY_mesh = o3d.t.geometry.TriangleMesh()
            registered.append(TY)    

        return registered

    @staticmethod
    def affine_registration(target: o3d.geometry.TriangleMesh, source: o3d.geometry.TriangleMesh, callback) -> o3d.geometry.TriangleMesh:
        X = np.asarray(target.vertices)
        Y = np.asarray(source.vertices)
        
        reg = AffineRegistration(X = X, Y = Y, max_iterations = 1000)
        if callback is None:
            _, (R, t) = reg.register()
        else:
            _, (R, t) = reg.register(callback)

        TY = copy.deepcopy(source)
        TY.rotate(R)
        TY.translate(t)

        return TY
    
    @staticmethod
    def soft_registration(target: o3d.geometry.TriangleMesh, source: o3d.geometry.TriangleMesh):
        X = np.asarray(target.vertices)
        Y = np.asarray(source.vertices)
        Yt = np.asarray(source.triangles)
        
        tradeoff = 0.005
        width = 2

        reg = DeformableRegistration(X = X, Y = Y, alpha = tradeoff, beta = width)
        TY, (G, V) = reg.register()

        TY = o3d.t.geometry.TriangleMesh(TY, Yt).to_legacy()

        return TY

#     def calculate_vecor_field(initial: o3d.geometry.TriangleMesh, result: o3d.geometry.TriangleMesh):
#         X = np.asarray(initial.vertices)
#         Y = np.asarray(result.vertices)
#         vector_field = X - Y
#         magnitudes = np.linalg.norm(vector_field, axis = 1)
#         return vector_field, magnitudes

    @staticmethod
    def calculate_average_mesh(measurements: List[o3d.geometry.TriangleMesh]) -> o3d.geometry.TriangleMesh:
        """Returns a statistical average mesh given a list of triangle meshes.
        
        Args:
            measurements:
                A list of o3d.geometry.TriangleMesh objects. The first element will be the basis for the construction of the average shape.
        """
        if len(measurements) == 0:
            print("You need to supply a list of CBM measurements to be registered.")
            return

        if len(measurements) == 1:
            return (measurements[0])
        
        V = np.asarray(measurements[0].vertices)
        T = np.asarray(measurements[0].triangles)

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

        # Reference for plot    
        reference = o3d.t.geometry.TriangleMesh(V, T)
        reference = reference.to_legacy()

        # Construct the average mesh
        TV = V + average_displacement_vectors
        average_mesh = o3d.t.geometry.TriangleMesh(TV, T)
        norm = mpl.colors.Normalize(np.min(magnitudes), np.max(magnitudes))
        cmap = cm.GnBu
        m = cm.ScalarMappable(norm = norm, cmap = cmap)
        colours = m.to_rgba(magnitudes)
        colours = colours[:, 0:3]
        average_mesh.vertex.colors = colours
        average_mesh = average_mesh.to_legacy()

        return average_mesh