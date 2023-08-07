import numpy as np

def rotate_x(M, angle: float):
    th = np.deg2rad(angle)
    R = np.array([
        [1.0, 0.0,        0.0,         0.0],
        [0.0, np.cos(th), -np.sin(th), 0.0],
        [0.0, np.sin(th), np.cos(th),  0.0],
        [0.0, 0.0,        0.0,         1.0]])
    return M @ R


def translate(M, t):
    T = np.array([
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [t[0], t[1], t[2], 1.0]])
    return M @ T


class CbmMeasurement():
    def __init__(self, name, base, back, pointer, angle) -> None:
        self.type = "CBM Measurement"
        self.name = name
        self.x_resolution = 0.04445 # Metres
        self.y_resolution = 0.04445 # Metres
        self.max_pin_displacement = 101.6 # 4 inches converted to millimetres

        self.height_from_base_to_back = 2 # cm
        self.depth_from_measured_pin_to_rotation_axis = 21.5 # cm
        self.height_from_measured_pin_to_rotation_axis = 2 # cm
        self.measured_pin_position = 9 * self.y_resolution

        # Convert stuff to metres
        self.max_pin_displacement = self.max_pin_displacement / 1000 # mm to metres
        self.height_from_base_to_back = self.height_from_base_to_back / 100 # cm to metres
        self.depth_from_measured_pin_to_rotation_axis = self.depth_from_measured_pin_to_rotation_axis / 100 # cm to metres
        self.height_from_measured_pin_to_rotation_axis = self.height_from_measured_pin_to_rotation_axis / 100 # cm to metres

        # Assign passed in arguments
        self.base_matrix = base
        self.back_matrix = back

        # These values are used for rotating the matrices into the correct orientation
        self.pointer_position = pointer / 100 # cm to metres
        self.recline_angle = angle

        # Construct the mesh
        self.initialise()

    def initialise(self):
        """Creates the vertices and triangles that represent the measurement.
        
        The method creates the list of vertices, self.V, triangles, self.T, and normals self.N.
        The method also applies any transformations to ensure the meshes are in the correct orientation.

        Returns:
            None
        """
        V1 = self.create_vertices(self.base_matrix, self.base_model_matrix)
        V2 = self.create_vertices(self.back_matrix, self.back_model_matrix)

        T1 = self.create_triangles(self.base_matrix)
        T2 = self.create_triangles(self.back_matrix)

        # Remove points which are behind the back rest
        V1, T1 = self.remove_unused_pins(V1, T1)

        # Adjust T2 so that the vertex numbers correspond to the vertices in V2 after the concatenation below.
        number_of_vertices_in_v1, _ = np.shape(V1)
        T2 = np.add(T2, number_of_vertices_in_v1)

        V = np.concatenate([V1, V2])
        T = np.concatenate([T1, T2])

        N = self.create_normals(V, T)

        self.V = V
        self.T = T
        self.N = N

    
    @property
    def base_model_matrix(self):
        """Gets the matrix representing the base cushion's transformation.
        """
        M = np.identity(4, dtype = float)
        return M
        

    @property
    def back_model_matrix(self):
        """Gets the matrix representing the back cushion's transformation.

        The matrix is constructed based on the supplied recline angle and pointer position.
        """
        M = np.identity(4, dtype = float)

        # Orient the measurement so it is in the correct starting orientation
        M = rotate_x(M, -90)
        
        # Rotate the back rest at the correct axes of rotation
        M = translate(M, [0, -self.depth_from_measured_pin_to_rotation_axis, -self.height_from_measured_pin_to_rotation_axis])
        M = rotate_x(M, self.recline_angle - 90)
        M = translate(M, [0, self.depth_from_measured_pin_to_rotation_axis, self.height_from_measured_pin_to_rotation_axis])
                
        # Translate to 31 cm pointer position as this is where the backrest aligns with the last pin of the base.
        # This then allows for adjustment of the pointer position
        M = translate(M, [0, self.pointer_position, 0])

        # Create the gap between the back and base
        M = translate(M, [0, 0 , self.height_from_base_to_back])

        return M


    def create_vertices(self, M, T):
        """Creates an np.array of x, y, z coordinates for a given mesh and transformation matrix.
        
        Args:
            M: A m by n matrix representing the CBM measurement.
            T: A 4 by 4 matrix representing a transformation for this measurement.

        Returns:
            V: A np.array of (X, 3) in size where each row is a vertex position.
        """

        (number_of_rows, number_of_columns) = np.shape(M)
        z = -np.reshape(M, [number_of_rows * number_of_columns])
        x = np.hstack([[x for x in range(number_of_columns)] for y in range(number_of_rows, 0, -1)]) * self.x_resolution
        y = np.hstack([[y-1 for x in range(number_of_columns)] for y in range(number_of_rows, 0, -1)]) * self.y_resolution
        w = np.ones(number_of_rows * number_of_columns)

        V = np.array([x, y, z, w]).T

        # Apply the transformation for this set of vertices
        V = V @ T

        # Remove the w column
        V = V[:, 0:3]

        return V
    

    def create_triangles(self, M):
        """Returns a triangle mesh representation of a CBM measurement.

        Args:
            M: A m by n matrix representing the CBM measurement.

        Returns:
            T: A np.array of (Y, 3) in size where each row are vertex indices making up a triangle
        
        Raises:
            ValueError:
                When the number of rows or columns in either of the measurement matrices are less than 2.
        """

        (number_of_rows, number_of_columns) = np.shape(M)

        if number_of_rows < 2:
            raise ValueError("Number of rows is less than 2, unable to create triangles.")

        if number_of_columns < 2:
            raise ValueError("Number of columns is less than 2, unable to create triangles.")

        number_of_squares = (number_of_rows - 1) * (number_of_columns - 1)
        number_of_triangles = 2 * number_of_squares

        T = np.zeros([number_of_triangles, 3], dtype = int)

        for idx in range(number_of_squares):
            v1 = idx + (idx // (number_of_columns - 1))
            v2 = v1 + 1
            v3 = v2 + number_of_columns
            v4 = v1 + number_of_columns

            # Triangle should be constructed anti-clockwise
            t1 = np.array([v1, v3, v2], ndmin = 2, dtype = int)
            t2 = np.array([v3, v1, v4], ndmin = 2, dtype = int)

            t1_index = 2 * idx
            t2_index = t1_index + 1
            T[t1_index, :] = t1
            T[t2_index, :] = t2

        return T
    

    def create_normals(self, V, T):
        """Calculates the normals for each triangle in the given vertex and triangle arrays.
        
        Args:
            V:
                A m by 3 matrix where each row corresponds to the x, y, z, component of a vertex.
            T:
                A m by 3 matrix where each row contains an index to the three vertices in V that make up the triangle.
                
        Return:
            N:
                An array of normals, each row corresponds to a triangle in T.
        """

        number_of_triangles, _ = np.shape(T)
        v1 = np.array([1, 0, 0])
        v2 = np.array([0, 1, 0])

        N = np.zeros([number_of_triangles, 3])

        for i in range(number_of_triangles):
            v1 = V[T[i, 0], :]
            v2 = V[T[i, 1], :]
            v3 = V[T[i, 2], :]

            n = np.cross(v1 - v3, v1 - v2)
            N[i] = n

        return N
    

    def remove_unused_pins(self, V, T):
        theta = (self.recline_angle - 90) * (np.pi / 180)
        cutoff_depth = self.pointer_position - (self.height_from_measured_pin_to_rotation_axis * np.tan(theta))

        vertices_to_remove = ~np.greater_equal(V[:,1], cutoff_depth)
        V = V[vertices_to_remove, :]

        # Get the indices of the removed vartices so that we can remove the triangles
        indices = [i for i, v in enumerate(vertices_to_remove) if v == False]

        # Check which triangles contain a reference to the removed vertices and remove them
        triangles_to_remove = np.isin(T, indices)
        triangles_to_remove = ~np.any(triangles_to_remove, axis = 1)
        T = T[triangles_to_remove, :]

        # Adjust the numbering to match the new array of vertices
        minimum_vertex_number = np.min(T)
        T = np.subtract(T, minimum_vertex_number)

        return V, T