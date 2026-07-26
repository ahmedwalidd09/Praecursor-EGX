from .database import connect
from .schema import SCHEMA


def initialize_database():

    connection = connect()

    cursor = connection.cursor()

    cursor.executescript(SCHEMA)

    connection.commit()

    connection.close()

    print("Database schema initialized.")