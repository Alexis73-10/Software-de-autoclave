#este archivo permitira crear la conexión para que python permita escribir y leer archivos Parquet, acá se almacenará la trazabilidad o logs de los procesos y fases del autoclave
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from typing import Optional

class ParquetDB:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.engine: Optional[Engine] = None

    def connect(self):
        # En este caso, no es necesario crear una conexión como en bases de datos tradicionales,
        # pero podemos definir un motor para futuras expansiones si es necesario.
        self.engine = create_engine('sqlite:///:memory:')  # Placeholder engine

    def write_log(self, data: pd.DataFrame):
        table = pa.Table.from_pandas(data)
        pq.write_table(table, self.file_path)

    def read_log(self) -> pd.DataFrame:
        table = pq.read_table(self.file_path)
        return table.to_pandas()