import json
import re
import sqlite3
import sys
import threading

from pymongo import MongoClient, errors, database
from typing import Union

from . import make_sql as sql


# class Data(str):
# 	classes: list = []
#
# 	def __new__(cls, *args, **kwargs):
# 		if not cls.classes:
# 			cls.classes = cls.__subclasses__()
# 		thread_con = update_connection()
# 		for table in kwargs["tables"]:
# 			print(args[0], table)
#
# 		for cl in cls.classes:
# 			print(cl.__name__)
# 		raise RuntimeError("end of test")
#
# 	def __init__(self, _me: str, tables = None):
# 		self.me = _me
# 		self.tables = tables
#
# 	def __repr__(self):
# 		return self.me
#
# 	def __str__(self):
# 		return self.me
#
#
# class Users(Data):
# 	pass
#
#
# class Guilds(Data):
# 	pass


class ThreadCon:
	threads = {}

	def __init__(self, thread: threading.Thread, con: sqlite3.Connection, cur: sqlite3.Cursor):
		self.thread = thread
		self.con = con
		self.cur = cur
		self.threads[thread] = self

	@classmethod
	def get_con(cls, thread: threading.Thread):
		return cls.threads.get(thread)

	def commit(self):
		self.con.commit()


def update_connection() -> ThreadCon:
	if thread_con := ThreadCon.get_con(thread := threading.current_thread()):
		return thread_con
	else:
		con = sqlite3.connect("data/MyBot.db")
		con.row_factory = sqlite3.Row
		cur = con.cursor()
		return ThreadCon(thread, con, cur)


class Table(sql.Table):
	tables = {}

	def __new__(cls, data, from_schema = False):
		if from_schema:
			name, columns, foreign_keys = cls.from_schema(data)
			new_data = {
				"name": name,
				"columns": columns,
				"foreign_keys": foreign_keys
			}
		else:
			new_data = {
				"name": data,
			}

		if new_data["name"] in cls.tables:
			table = cls.tables[new_data["name"]]
			if str(table)[:-1] != data:
				table.__init__(new_data, from_schema)
		else:
			table = super().__new__(cls)
			cls.__init__(table, new_data, from_schema)
			cls.tables[new_data["name"]] = table
		return table

	def __init__(self, data, from_schema = False):
		if type(data) == str:
			return

		super().__init__(data["name"])

		if from_schema:
			columns = data["columns"]
			foreign_keys = data["foreign_keys"]
			func = (lambda x: "put_" + x.lower())
			for real_name, _type in columns:
				# print(name)
				_type = re.sub("\d+", "", _type)
				# print(_type)
				if len(splitted := _type.split(" ", 1)) > 1:
					_type = [splitted[0], True]
				else:
					_type = [_type, False]
				getattr(self, func(_type[0]))(real_name, _type[1])
			if foreign_keys:
				for foreign_key in foreign_keys:
					self.set_foreign_key(foreign_key[0], foreign_key[1])
		# print(self)

	def __eq__(self, other):
		return str(self) == str(other)

	@classmethod
	def from_schema(cls, data):
		# print(data)
		data = re.sub("CREATE TABLE ", "", data)
		name = re.search("[A-Za-z_0-9]+", data).group()
		# print(name)
		info = re.search("\((.*)\)$", data).group(1)
		if "FOREIGN" in info:
			temp = re.findall("\((.*?)\)", info)
			foreign = []
			for key, ref in zip(temp[::2], temp[1::2]):
				foreign.append((key, f"{key}({ref}"))
			info = re.sub(", FOREIGN .*", "", info)
		else:
			foreign = []
		ret = []
		for el in info.split(", "):
			temp = el.split(" ", 1)
			if "REFERENCES" in (val := temp[1]):
				temp2 = val.split()
				temp = [temp[0], temp2[0]]
				foreign.append([temp[0], temp2[-1]])
			ret.append(temp)
		# print("return from schema parser\n", name, ret, foreign)
		return name, ret, foreign

	def __getattr__(self, item):
		if item != "shape":
			pass
			# print("================ Table", item, "================")
		return self

	def rec_table(self, thread_con, data):
		# print("data", data)
		# set_primary = True
		func = (lambda x: "put_" + x.__class__.__name__)
		for column, value in data:
			if column in self._columns:
				continue
			# if "_" in column and type(value) != dict:
			# 	_db, key = column.split("_")
			# 	table_name = f"{_db.capitalize()}_{self._name}"
			# 	table = Table(table_name)
			# 	print("recreating table", table_name)
			# 	table.rec_table(thread_con, [(key, value)])
			# 	if "counting_id" not in self.__dir__():
			# 		self.put_serial("counting_id", set_primary)
			# 		set_primary = False
			# 	getattr(self, func(value))(column)
			# 	self.set_foreign_key(column, f"{table._name}({key})")

			# elif "_" in column and type(value) == dict:
			# 	table_name = "_".join(map(lambda x: x.capitalize(), column.split("_")))
			# 	table: Table = SQL.get_instance().get_collection(table_name)
			# 	print("updating table", table_name)
			# 	table.update_table(thread_con, list(value.items()))

			if type(value) == dict:
				sub_data = list(value.items())
				if not SQL.get_instance().tables.get(column):
					table: Table = Table(column)
					# print("recreating table", column)
					table.put_int("id_", True)
					table.rec_table(thread_con, sub_data)
					# print(table)
				else:
					pass
					# print(table)
					# thread_con.cur.execute(str(table))
				self.put_int(column)
				self.set_foreign_key(column, f"{column}(id_)")
			elif type(value) == list:
				if not SQL.get_instance().tables.get(column):
					table = Table(column)
					table.put_int("id_", True)
					new_data = map(lambda x: ("EL_" + str(x[0]), x[1]), enumerate(value))
					table.rec_table(thread_con, new_data)
				self.put_int(column)
				self.set_foreign_key(column, f"{column}(id_)")
			else:
				getattr(self, func(value))(column)  # , set_primary)
				# set_primary = False
		# SQL.get_instance().update_tables()
		try:
			thread_con.cur.execute(str(self))
			thread_con.commit()
		except Exception as e:
			raise e
		SQL.update_tables()
		return self

	def update_table(self, thread_con, data):
		# print("="*50 + f"\nupdate {self._name} with {data}\n" + "="*50)
		thread_con.cur.execute(f"PRAGMA table_info({self._name})")
		existing = [row[1] for row in thread_con.cur.fetchall()]
		ref = list(filter(lambda x: x[0] in existing, data))
		new_data = list(filter(lambda x: x[0] not in existing, data))
		# print("existing", existing)
		# print("ref", ref)
		# print("new_data", new_data)
		for column, value in new_data:
			# print("column&value", column, value)
			if type(value) == dict:
				table: Table = SQL.get_instance().get_collection(column)
				# print(table)
				ret = table.insert_one(value)
				stmt = f"ALTER TABLE {self._name} ADD {column} {sql.Datatypes.bigint} REFERENCES {column}(id_);"
				# print(stmt)
				thread_con.cur.execute(stmt)
				thread_con.con.commit()
				# print("updated with dict val")
			elif type(value) == list:
				raise RuntimeError("list value", value)
			else:
				stmt = f"ALTER TABLE {self._name} ADD {column} {getattr(sql.Datatypes, value.__class__.__name__)};"
				# print("stmt", stmt)
				thread_con.cur.execute(stmt)
				thread_con.con.commit()

		SQL.update_tables()
		return self

	def check_and_fix_integrity(self, thread_con, stmt, data, other = True):
		try:
			# print(stmt)
			thread_con.cur.execute(stmt)

		except sqlite3.OperationalError as e:
			if "no such column" in str(e) and other:
				if len(self._columns) == 1:
					# print(f"recreating table {self._name}")
					thread_con.cur.execute(f"DROP TABLE {self._name};")
					thread_con.commit()
					self.rec_table(thread_con, data)
				else:
					# print(f"adding column(s) to table {self._name}")
					self.update_table(thread_con, data)
					# thread_con.cur.execute(stmt)
				# print(self)
			else:
				raise e

	@staticmethod
	def fix_data(func):
		"""
		Walk data to turn lists in dicts or json
		"""

		def fix_list(data: list, info):

			if data:
				base = type(data[0])
				for el in data[:]:
					if type(el) != base:
						idx = data.index(el)
						temp = data.pop(idx)
						if base == dict:
							val = {"__SINGLE_ELEMENT__": temp}
						elif base == list:
							val = ["__SINGLE_ELEMENT__", temp]
						else:
							val = temp
						data.insert(idx, val)

			if data and (type(data[0]) == dict):
				# res = []
				res = dict(map(lambda x: ("EL_" + str(x[0]), fix_dict(x[1], info)), enumerate(data)))
				# for el in data:
				# 	res.append(fix_dict(el, info))
			elif data and (type(data[0]) == list):
				res = dict(map(lambda x: ("EL_" + str(x[0]), fix_list(x[1], info)), enumerate(data)))
			else:
				res = json.dumps(data, ensure_ascii = False)
			return res

		def fix_dict(data: dict, info):
			for key, val in list(data.items()):
				if key == "id_":
					raise RuntimeError("Using 'id_' as key will drop and recreate the currently used table!!")
				elif key.startswith("$"):
					temp = data.pop(key)
					info[key.strip("$").upper()] = list(temp.keys())
					data.update(temp)
			# print(data)

			for key, val in list(data.items()):
				if key == "id_":
					raise RuntimeError("Using 'id_' as key will drop and recreate the currently used table!!")
				elif type(val) == dict:
					res = fix_dict(val, info)
				elif type(val) == list:
					if "_LIST" not in key:
						data.pop(key)
						for k, lis in info.items():
							if key in lis:
								info[k][info[k].index(key)] = key + "_LIST"
						key = key + "_LIST"
						res = fix_list(val, info)
					else:
						res = val
				else:
					continue
				data[key] = res
			return data

		def wrapper(*args, **kwargs):
			data = args[-1]
			info: dict[str, list] = {}
			key: str
			# print(update)
			fix_dict(data, info)
			if kwargs:
				kwargs.update({"info": info})
			return func(*args, **kwargs)
		return wrapper

	def update(
		self,
		where: list[tuple[str, Union[str, int]]],
		data: dict,
		info: dict[str, list[str]],
		upsert = False
	):
		thread_con = update_connection()
		keys = list(data.keys())
		# print(keys)
		where = list(zip(*where))
		where_stmt = f"WHERE {'=? and '.join(where[0])}=?"
		find = f"SELECT * FROM {self._name} {where_stmt};"
		# print(find)
		# raise RuntimeError("test done")
		thread_con.cur.execute(find, where[1])
		res = thread_con.cur.fetchone()
		if not res:
			if not upsert:
				raise LookupError(f"Can't update {self._name} as no entry matching '{where_stmt}' with {where[1]} could be found!")
			else:
				return self.insert_one(data)
		to_set = "=?,".join(info['SET']) + "=?"

		for el in info.get("SETONINSERT") or []:
			data.pop(el)
		stmt = f"UPDATE {self._name} SET {to_set} {where_stmt}"
		# print("prepare", stmt)
		values = []
		update = []
		for key, value in data.items():
			if type(value) == dict:
				table: Table = SQL.get_instance().get_collection(key)
				to_append = table.find_one(value)["id_"]
			elif type(value) == list:
				raise RuntimeError(value)
			else:
				to_append = value
			if key not in where:
				update.append(to_append)
		update.extend(where[1])
		# print("statement & values", stmt, [*values, *update])
		ret = thread_con.cur.execute(stmt, [*values, *update])
		thread_con.commit()
		return ret

	@fix_data
	def update_one(
		self,
		_filter: dict,
		_update: dict,
		info: dict[str, list[str]],
		upsert = False
	):
		thread_con = update_connection()
		# print("="*50 + f"\ntrying to update {self._name} by {_filter} with {_update} and {info}\n" + "="*50)
		data = [*_filter.items(), *_update.items()]
		stmt = f"SELECT {','.join(set(list(zip(*data))[0]))} FROM {self._name};"
		self.check_and_fix_integrity(thread_con, stmt, data, upsert)
		self.update(list(_filter.items()), _update, info, upsert)
		return self

	def insert(self, data: dict) -> int:
		thread_con = update_connection()
		stmt = f"INSERT INTO {self._name}({','.join(data.keys())}) VALUES({','.join(['?'] * len(data))});"
		values = []
		for key, val in data.items():
			if type(val) == dict:
				table: Table = SQL.get_instance().tables[key]
				if not (check := table.find_one(val)):
					res = table.insert_one(val)
				else:
					res = check["id_"]
			elif type(val) == list:
				table = SQL.get_instance().tables[key]
				values = dict(map(lambda x: ("EL_" + str(x[0]), x[1]), enumerate(val)))
				if not (check := table.find_one(values)):
					res = table.insert_one(values)
				else:
					res = check["id_"]
				# raise RuntimeError(val)
			else:
				res = val
			values.append(res)
		ret = thread_con.cur.execute(stmt, values)
		thread_con.commit()
		return self.find_one({"rowid": ret.lastrowid}, {"id_": True})["id_"]

	@fix_data
	def insert_one(self, to_insert: dict):
		thread_con = update_connection()
		# print("="*50 + f"\ntrying to insert {to_insert} in {self._name}\n" + "="*50)
		data = to_insert.items()

		stmt = f"SELECT {','.join(list(zip(*data))[0])} FROM {self._name};"
		self.check_and_fix_integrity(thread_con, stmt, data)
		return self.insert(to_insert)

	def find(
		self,
		_filter: dict = None,
		_projection: dict = None,
		limit: int = None
	):
		thread_con = update_connection()
		# print("="*50 + f"\ntrying to find {_filter} in {self._name}\n" + "="*50)
		if not _filter:
			thread_con.cur.execute(f"SELECT * from {self._name};")
			results = [dict(r) for r in thread_con.cur.fetchall()][:limit]
		else:

			# print(_filter, _projection, limit)
			search = {}
			for key, val in list(_filter.items()):
				if type(val) == dict:
					table = SQL.get_instance().tables[key]
					val = table.find_one(val, {"id_": True})
					val = val["id_"] if val else ''
				search[key] = val
			orig_data = list(_filter.items())
			data = list(search.items())
			stmt = f"SELECT * from {self._name} WHERE " \
				f"{' AND '.join([' = '.join([item[0], repr(item[1])]) for item in data])};"
			self.check_and_fix_integrity(thread_con, stmt, orig_data)
			temp = thread_con.cur.fetchall()
			results = [dict(r) for r in temp][:limit]
			# print("results of find", results)

			if results and (temp := list(filter(lambda x: any(y in x for y in self._foreign_keys), results))):
				for temp_res in temp:
					# print(temp_res)
					for key, val in temp_res.items():
						table: Table = SQL.get_instance().tables.get(key)
						if table:
							res = table.find_one({"id_": val}, _projection)
							res.pop("id_")
							for result in results:
								result[key] = res
				# print("results of find after adapting dict", results)
		for result in results:
			if _projection:
				temp = set(result.keys()).difference(_projection.keys())
				for key in temp:
					result.pop(key)
			for key, val in list(result.items()):
				if "_LIST" in key:
					result.pop(key)
					key = key.strip("_LIST")
					if type(val) == dict:
						if test := val.get("__SINGLE_ELEMENT__"):
							val = test
					elif type(val) == list:
						if val[0] == "__SINGLE_ELEMENT__":
							val = val[1]
					else:
						val = json.loads(val)
					result[key] = val

		# print("results after projection applied", results)
		return results

	def find_one(
		self,
		_filter: dict = None,
		_projection: dict = None
	):
		ret = self.find(_filter, _projection, 1)
		return ret[0] if ret else None


class SQL:
	_instance = None

	def __new__(cls):
		if not cls._instance:
			cls._instance = super().__new__(cls)
		return cls._instance

	def __init__(self):
		self.tables: dict[str, Table] = {}
		self.update_tables()

	@classmethod
	def get_instance(cls):
		return cls._instance

	@classmethod
	def update_tables(cls):
		# print("UPDATING INTERNAL TABLES")
		instance = cls.get_instance()
		thread_con = update_connection()
		thread_con.cur.execute("SELECT * FROM sqlite_master WHERE type='table';")
		for table in thread_con.cur.fetchall():
			# print("found", table)
			instance.tables[table[1]] = Table(table[-1], from_schema = True)
		# print("tables", self.tables)

	def __getattr__(self, item):
		if item != "shape":
			pass
			# print("================ SQL", item, "================")
		return self

	def get_collection(self, name):
		if name not in self.tables:
			thread_con = update_connection()
			# print("================ make table", name, "================")
			table = Table(name)
			# print(table)
			thread_con.cur.execute(str(table))
			self.update_tables()
			# self.tables[name] = table
		else:
			# print("================ get table", name, "================")
			table = self.tables[name]
			# print(table)
		return table


class Mongo:
	__slots__ = ["db", "sql"]

	def __new__(cls, sql_fallback):
		try:
			client = MongoClient(serverSelectionTimeoutMS = 5000)
			client.admin.command("ping")
			instance = super().__new__(cls)
			instance.__setattr__("db", client.get_database(name = "MyBot"))
			instance.__setattr__("sql", sql_fallback)
			# instance._update()
		except errors.ConnectionFailure:
			# print("mongodb connection failure, using SQL")
			instance = sql_fallback
		# instance = super().__new__(cls, sql)
		return instance

	# def __init__(self, sql_fallback):
		# print("init with", sql_fallback)
	# 	self.db: database.Database
	# 	self.sql: SQL

	# def __del__(self):
		# self._update(False)

	# def _update(self, up = True):
	# 	if up:
	# 		pass
	# 		# print(self.sql)
	# 	else:
	# 		pass
	# 		# print(self.db)


class DB:
	def __init__(self):
		self.db = Mongo(SQL())

	def __getattr__(self, item):
		return getattr(self.db, item)


db = DB()
# print(db)
