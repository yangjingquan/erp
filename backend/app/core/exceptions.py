class AppError(Exception):
    def __init__(self, msg: str, code: int = 400, data: object = None) -> None:
        super().__init__(msg)
        self.code = code
        self.msg = msg
        self.data = data
