class Vertex:
    def __init__(self, vertex_id,f,s):
        self.vertex_id = vertex_id
        self.f = f #function
        self.s = s #system 


class WFGraph:
    def __init__(self):
        self.vertices = {}
        self.adj = {}

    def add_vertex(self, vertex):
        self.vertices[vertex.vertex_id] = vertex
        self.adj.setdefault(vertex.vertex_id, [])

    def add_edge(self, from_vertex, to_vertex):
        if from_vertex in self.vertices and to_vertex in self.vertices:
            self.adj[from_vertex].append(to_vertex)

    def add_edges(self, edge_list):
        for from_id, to_id in edge_list:
            if from_id not in self.vertices:
                self.add_vertex(Vertex(from_id))
            if to_id not in self.vertices:
                self.add_vertex(Vertex(to_id))
            self.add_edge(from_id, to_id)

    def get_neighbors(self, vertex_id):
        return self.adj.get(vertex_id, [])

    def find_vertex(self, field_name, value):
        for vertex in self.vertices.values():
            if getattr(vertex, field_name, None) == value:
                return vertex
        return None
    
    def find_path(self, start_id, end_id):
        visited = set()
        path = []

        def dfs(current):
            if current == end_id:
                path.append(current)
                return True
            if current in visited:
                return False
            visited.add(current)
            path.append(current)
            for neighbor in self.adj.get(current, []):
                if dfs(neighbor):
                    return True
            path.pop()
            return False

        if dfs(start_id):
            return path
        return None
    
    def vertex_on_path(self, vertex_id, path_list):
        return vertex_id in path_list


