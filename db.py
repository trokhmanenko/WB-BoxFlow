import sqlite3
import os
import shutil
from datetime import datetime
from typing import List, Union, Dict, Any, Optional
from aiogram.types import Message
import random
import string
from auth_data import MAX_FREE_USAGE_LIMIT, admins
import pandas as pd


class Database:
    TABLE_DEFINITIONS = {
        "users": [
            ("user_id", "INTEGER PRIMARY KEY"),
            ("first_name", "TEXT"),
            ("last_name", "TEXT"),
            ("username", "TEXT"),
            ("password", "TEXT"),
            ("usage_limit", "INTEGER"),
            ("is_authorized", "INTEGER DEFAULT 0"),
            ("registration_date", "TEXT"),
            ("amount_of_boxes", "INTEGER DEFAULT 0"),
        ],
        "files": [
            ("user_id", "INTEGER PRIMARY KEY"),
            ("box_capacity_id", "TEXT"),
            ("items_to_ship_id", "TEXT"),
            ("boxes_id", "TEXT"),
        ],
        "generations": [
            ("generation_id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
            ("user_id", "INTEGER"),
            ("generation_date", "TEXT"),
        ]
    }

    def __init__(self, db_file: str) -> None:
        self.db_file = db_file
        self.connection = sqlite3.connect(db_file)
        self.connection.row_factory = sqlite3.Row
        self.cursor = self.connection.cursor()

    def initialize_database(self) -> None:
        backup_dir = "backups"

        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)

        backup_db_path = os.path.join(
            backup_dir,
            f"{os.path.basename(self.db_file[:-3])}_backup_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.db"
        )

        shutil.copy2(self.db_file, backup_db_path)
        print(f"Backup created at {backup_db_path}")

        with self.connection:
            for table, definition in self.TABLE_DEFINITIONS.items():
                temp_table_name = f"{table}_temp"

                # Получаем список всех таблиц
                self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                all_tables = [row['name'] for row in self.cursor.fetchall()]

                # Если таблица существует, копируем её во временную
                if table in all_tables:
                    self.cursor.execute(f"DROP TABLE IF EXISTS {temp_table_name}")
                    self.cursor.execute(f"CREATE TABLE {temp_table_name} AS SELECT * FROM {table}")
                    self.cursor.execute(f"DROP TABLE {table}")

                # Создаем новую таблицу с обновленными определениями
                columns = ", ".join([f"{col_name} {col_definition}" for col_name, col_definition in definition])
                self.cursor.execute(f"CREATE TABLE {table} ({columns})")

                # Если таблица существовала и была скопирована, копируем данные обратно
                if table in all_tables:
                    self.cursor.execute(f"PRAGMA table_info({temp_table_name});")
                    temp_table_cols = [row["name"] for row in self.cursor.fetchall()]

                    # Получите столбцы для новой таблицы из definition
                    new_table_cols = [col[0] for col in definition]

                    # Определите общие столбцы между двумя таблицами
                    common_cols = ", ".join([col for col in new_table_cols if col in temp_table_cols])
                    self.cursor.execute(
                        f"INSERT INTO {table} ({common_cols}) SELECT {common_cols} FROM {temp_table_name}")
                    self.cursor.execute(f"DROP TABLE {temp_table_name}")
            print("Database is initialized")

    def get_row_as_dict(self,
                        conditions: Dict[str, Any],
                        table_names: Union[List[str], str] = None) -> Union[Dict[str, Any], None]:
        data = {}

        if table_names is None:
            table_names = ['users', 'files']

        if isinstance(table_names, str):
            table_names = [table_names]

        for table_name in table_names:
            # Формируем строку для WHERE
            where_str = " AND ".join([f"{col} = ?" for col in conditions.keys()])

            query = f"""
                    SELECT * 
                    FROM {table_name}
                    WHERE {where_str}
                """

            row = self.cursor.execute(query, tuple(conditions.values())).fetchone()

            if row is not None:
                data.update(dict(row))

        return data if data else None

    def insert_into_table(self, table_name: str, values: Dict[str, Any]) -> None:
        with self.connection:
            cursor = self.connection.cursor()

            # Формируем строку для колонок и значения
            columns_str = ", ".join(values.keys())
            values_str = ", ".join(["?" for _ in values])

            # Формируем SQL-запрос
            sql = f"INSERT INTO {table_name} ({columns_str}) VALUES ({values_str})"

            # Выполняем запрос
            cursor.execute(sql, list(values.values()))

    def update_table(self, table_name: str, values: Dict[str, Any],
                     conditions: Dict[str, Any]) -> Union[Dict[str, Any], None]:
        """
        Обновляет значения в указанной таблице и возвращает обновленную строку.

        :param table_name: Имя таблицы для обновления.
        :param values: Словарь с новыми значениями { 'column1': new_value1, 'column2': new_value2, ... }.
        :param conditions: Словарь с условиями для WHERE { 'column1': value1, 'column2': value2, ... }.
        :return: Обновленная строка или None, если строка не найдена.
        """
        with self.connection:
            # Формируем строку для SET
            set_str = ", ".join([f"{col} = ?" for col in values.keys()])

            # Формируем строку для WHERE
            where_str = " AND ".join([f"{col} = ?" for col in conditions.keys()])

            # Формируем SQL-запрос
            sql = f"UPDATE {table_name} SET {set_str} WHERE {where_str}"

            # Выполняем запрос
            self.cursor.execute(sql, list(values.values()) + list(conditions.values()))

        # Получаем и возвращаем обновленную строку
        return self.get_row_as_dict(conditions, table_name)

    def create_user(self, message: Message) -> Dict[str, Any]:
        user_id = message.from_user.id
        user_data = self.get_row_as_dict({'user_id': user_id}, ['users'])

        if user_data is None:
            # Создание нового пользователя
            user_data = {
                "user_id": user_id,
                "first_name": message.from_user.first_name,
                "last_name": message.from_user.last_name or "Not specified",
                "username": message.from_user.username,
                "password": self.generate_password(),
                "usage_limit": MAX_FREE_USAGE_LIMIT,
                "is_authorized": 1 if message.from_user.username in admins else 0,
                "registration_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            self.insert_into_table("users", user_data)
            self.insert_into_table("files", {"user_id": user_id, "box_capacity_id": None, "items_to_ship_id": None,
                                             "boxes_id": None})
        return user_data

    def update_user(self, user_id: int) -> Dict[str, Any]:
        user_data = self.get_row_as_dict({'user_id': user_id})
        user_data["password"] = self.generate_password()
        user_data["is_authorized"] = 1 if user_data["username"] in admins else 0
        self.update_table("users", {"password": user_data["password"], "is_authorized": user_data["is_authorized"]},
                          {"user_id": user_id})
        self.reset_file_ids(user_id)
        return user_data

    @staticmethod
    def generate_password():
        length = random.randint(10, 20)
        characters = string.ascii_letters + string.digits + string.punctuation

        # Генерируйте пароль
        password = ''.join(random.choice(characters) for _ in range(length))

        return password

    def decrease_usage_limit(self, user_id: int) -> int:
        with self.connection:
            user_data = self.get_row_as_dict({'user_id': user_id}, 'users')
            if user_data is None:
                return 0  # Если данные пользователя не найдены, возвращаем 0

            if user_data['is_authorized']:
                return user_data['usage_limit']  # Если пользователь авторизован, возвращаем текущий лимит

            new_limit = max(user_data['usage_limit'] - 1, 0)  # Уменьшаем лимит на 1, но не меньше 0
            self.cursor.execute("UPDATE users SET usage_limit=? WHERE user_id=?", (new_limit, user_id))
            return new_limit

    def toggle_authorization(self, user_id: int, authorize: bool = True) -> None:
        user_data = self.get_row_as_dict({'user_id': user_id}, 'users')
        if user_data:
            new_auth_status = 1 if authorize else 0
            self.update_table("users", {"is_authorized": new_auth_status}, {"user_id": user_id})

    def create_generation(self, user_id) -> None:
        generation_data = {
            "user_id": user_id,
            "generation_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        # Используем существующий метод для вставки данных в таблицу
        self.insert_into_table("generations", generation_data)

    def save_dataframe(self, user_id, table_name: str, df: pd.DataFrame):
        if df.empty:
            return False

        # Запись или обновление данных в таблице
        try:
            df.to_sql(name=str(user_id) + table_name, con=self.connection, if_exists='replace', index=False)
            self.update_table('files', {table_name: str(user_id) + table_name}, {'user_id': user_id})
            return True
        except Exception as e:
            print(f"Ошибка при сохранении данных в таблицу {table_name}: {e}")
            return False

    def reset_amount_of_boxes(self, user_id):
        return self.update_table("users", {"amount_of_boxes": 0}, {"user_id": user_id})

    def reset_file_ids(self, user_id: int, columns: List[str] = None) -> None:
        columns_to_reset = columns or ["box_capacity_id", "items_to_ship_id", "boxes_id"]
        self.update_table("files", {col: None for col in columns_to_reset}, {"user_id": user_id})

    def get_data_from_db(self, user_id: int) -> List[Optional[pd.DataFrame]]:
        # Получаем имена таблиц из базы данных
        user_data = self.get_row_as_dict({'user_id': user_id}, 'files')
        box_capacity_table_name = user_data.get('box_capacity_id')
        items_to_ship_table_name = user_data.get('items_to_ship_id')
        boxes_id_table_name = user_data.get('boxes_id')

        box_capacity_df, items_to_ship_df, boxes_id_df = None, None, None

        try:
            if box_capacity_table_name:
                # Чтение данных о вместимости товаров в коробку из базы данных в датафрейм
                query_box_capacity = f'SELECT * FROM "{box_capacity_table_name}"'
                box_capacity_df = pd.read_sql_query(query_box_capacity, self.connection)

            if items_to_ship_table_name:
                # Чтение данных о количестве товаров из базы данных в датафрейм
                query_items_to_ship = f'SELECT * FROM "{items_to_ship_table_name}"'
                items_to_ship_df = pd.read_sql_query(query_items_to_ship, self.connection)

            if boxes_id_table_name:
                # Чтение данных о названиях коробок из базы данных в датафрейм
                query_boxes_id = f'SELECT * FROM "{boxes_id_table_name}"'
                boxes_id_df = pd.read_sql_query(query_boxes_id, self.connection)

        except Exception as e:
            print(f"Ошибка при чтении из базы данных: {e}")

        return [box_capacity_df, items_to_ship_df, boxes_id_df]
