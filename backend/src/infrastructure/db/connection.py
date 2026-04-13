class Database:
    def __init__(self, url: str) -> None:
        self.url = url

    async def connect(self) -> None:
        return None

    async def disconnect(self) -> None:
        return None


def create_database(url: str) -> Database:
    return Database(url)
