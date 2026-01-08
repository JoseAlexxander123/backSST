class SPRepository:
    def __init__(self, db):
        self.db = db

    def call(self, sp_query: str, params: dict = None):
        result = self.db.execute(sp_query, params or {})
        return result.fetchall()
