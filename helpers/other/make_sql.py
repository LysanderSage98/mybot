class Datatypes:
	"""
	Datendefinitionen
	"""
	bigint = "INTEGER"
	# bigserial = "BIGSERIAL"
	bit = (lambda x = 80: f"VARBIT({x if isinstance(x, int) else 80})")
	bit_varying = bit
	blob = "BLOB"
	bool = "BOOLEAN"
	char = (lambda x = 80: f"CHARACTER({x if isinstance(x, int) else 80})")
	character = char
	character_varying = (lambda x: f"VARCHAR({x if x and isinstance(x, int) else 80})")
	date = "DATE"
	decimal = (lambda x = 0, y = 0: f"DECIMAL({f'{abs(x)}, {abs(y)}' if isinstance(x, int) and y and isinstance(y, int) else f'{abs(x) if isinstance(x, int) else 0}'})")
	float = (lambda x: f"FLOAT{f'({x})' if x and isinstance(x, int) else ''}")
	int = "INT4"
	int2 = "INT2"
	int4 = int
	int8 = bigint
	Int64 = bigint
	integer = int
	numeric = decimal
	str = "TEXT"
	# serial = bigserial
	smallint = int2
	# smallserial = bigserial
	text = str
	time = "TIME"
	timestamp = "TIMESTAMP"
	varbit = bit
	varchar = character_varying


class Domain:
	
	def __init__(self, name):
		self._name = name
		self._datatype = ""
		self._default = ""
		self._check = ""
		self._pprint = False
		
	def pretty_print(self, val: bool):
		if isinstance(val, bool):
			self._pprint = val
		return self
	
	def get_name(self):
		return self._name
	
	def set_datatype(self, name: str):
		if isinstance(name, str):
			self._datatype = name
		else:
			raise RuntimeError(f"Needs to be a string, not {name.__class__}!")
		return self
	
	def set_default(self, default: str):
		if isinstance(default, str):
			self._default = f"{default.__repr__()}"
		else:
			raise RuntimeError(f"Needs to be a string, not {default.__class__}!")
		return self
	
	def set_check(self, check: str):
		"""
		Needs the part in the parentheses
		"""
		if isinstance(check, str):
			self._check = check
		else:
			raise RuntimeError(f"Needs to be a string, not {check.__class__}!")
		return self
	
	def __repr__(self):
		if self._pprint:
			append = "\n\t"
		else:
			append = ""
		out = f"CREATE DOMAIN {self._name}" + append
		if self._datatype:
			out += f" AS {self._datatype}" + append
		if self._default:
			out += f" DEFAULT {self._default}" + append
		if self._check:
			out += f" CHECK ({self._check})" + append
		return out.strip(append) + ";"


class Table:
	init = False  # because of debugger

	def __init__(self, name):
		self._name: str = name
		self._pprint = False
		self._columns = {}
		self._foreign_keys = {}
		self.init = True
		
	def clear(self):
		self._columns.clear()
		self._foreign_keys.clear()
	
	def _add_datatype(self, name, datatype, primary_key):
		if name.startswith("_"):
			raise NameError("Name may not start with underscore")
		elif ":" in name:
			temp = name.split(":")
			name = temp[0]
			datatype = (datatype, temp[1])
		if primary_key:
			datatype += " PRIMARY KEY"
		self._columns[name] = datatype

	def pretty_print(self, val: bool):
		"""
		Toggle pretty print on or off

		:param val: boolean
		"""
		self._pprint = bool(val)
		return self
	
	def put_int(self, name: str, primary_key = False):
		"""
		Ganze Zahl, 8 Byte
		"""
		datatype = Datatypes.bigint
		self._add_datatype(name, datatype, primary_key)
		return self
	
	# def put_serial(self, name: str, primary_key = False):
	# 	"""
	# 	Incremental counter
	# 	"""
	# 	datatype = Datatypes.serial
	# 	self._add_datatype(name, datatype, primary_key)
	# 	return self

	# def put_bigserial(self, name: str, primary_key = False):
	# 	"""
	# 	Incremental counter
	# 	"""
	# 	datatype = Datatypes.bigserial
	# 	self._add_datatype(name, datatype, primary_key)
	# 	return self
	
	def put_bit(self, name: str, primary_key = False, length: int = 0):
		"""
		Bit-String
		"""
		if length:
			datatype = f"VARBIT({length})"
			self._add_datatype(name, datatype, primary_key)
			return self
		else:
			raise RuntimeError("Length has to be bigger than 0!")
	
	def put_blob(self, name: str, primary_key = False):
		"""
		Binary Large Object, z.B. Bild
		"""
		datatype = Datatypes.blob
		self._add_datatype(name, datatype, primary_key)
		return self
	
	def put_bool(self, name: str, primary_key = False):
		"""
		Wahrheitswert
		"""
		datatype = Datatypes.bool
		self._add_datatype(name, datatype, primary_key)
		return self
	
	def put_char(self, name: str, primary_key = False, length: int = 0):
		"""
		String mit fester Länge
		"""
		if length:
			datatype = f"CHARACTER({length})"
			self._add_datatype(name, datatype, primary_key)
			return self
		else:
			raise RuntimeError("Length has to be bigger than 0!")
	
	def put_date(self, name: str, primary_key = False):
		"""
		Datum
		"""
		datatype = Datatypes.date
		self._add_datatype(name, datatype, primary_key)
		return self
	
	def put_decimal(self, name: str, primary_key = False, p: int = 0, q: int = 0):
		"""
		Fixkommaarithmetik
		"""
		datatype = f"DECIMAL({abs(p)},{abs(q)})" if q else f"DECIMAL({abs(p)})"
		self._add_datatype(name, datatype, primary_key)
		return self
	
	def put_domain(self, name: str, obj: Domain, primary_key = False):
		"""
		Eigener Datentyp
		"""
		datatype = obj.get_name()
		self._add_datatype(name, datatype, primary_key)
		return self
	
	def put_float(self, name: str, primary_key = False, genauigkeit: int = None):
		"""
		Gleitkommazahl mit optionaler Genauigkeit von 1 bis 15
		"""
		datatype = "FLOAT"
		if genauigkeit and isinstance(genauigkeit, int):
			genauigkeit = min(max(1, genauigkeit), 15)
			datatype += f"({genauigkeit})"
		self._add_datatype(name, datatype, primary_key)
		return self

	def put_str(self, name: str, primary_key = False):
		"""
		Beliebig lange Zeichenketten
		"""
		datatype = Datatypes.text
		self._add_datatype(name, datatype, primary_key)
		return self

	put_text = put_str

	put_integer = put_int
	
	put_int64 = put_int
	
	def put_time(self, name: str, primary_key = False):
		"""
		Uhrzeit
		"""
		datatype = Datatypes.time
		self._add_datatype(name, datatype, primary_key)
		return self
	
	def put_timestamp(self, name: str, primary_key = False):
		"""
		Datum und Uhrzeit
		"""
		datatype = Datatypes.timestamp
		self._add_datatype(name, datatype, primary_key)
		return self
	
	def put_varchar(self, name: str, primary_key = False, length: int = 0):
		"""
		String mit maximaler Länge
		"""
		if length:
			datatype = f"VARCHAR({length})"
			self._add_datatype(name, datatype, primary_key)
			return self
		else:
			raise RuntimeError("Length has to be bigger than 0!")
	
	def del_val(self, name: str):
		"""
		Spalte aus Create Table entfernen
		"""
		self._columns.pop(name)
		return self
	
	def set_foreign_key(self, name: str, ref: str):
		"""
		Verweis auf andere Tabelle
		
		:param name: Spaltename[n, kommasepariert] dieser Tabelle
		:param ref: Fremdtabelle(Spaltenname[n, kommasepariert])
		"""
		if not self._foreign_keys.get(name):
			self._foreign_keys[name] = [ref]
		else:
			self._foreign_keys[name].append(ref)
		return self

	def __repr__(self):
		return str(self.__dict__)

	def __str__(self):
		items = list(self._columns.items())
		if not items and self.init:
			self.put_int("id_", True)
			items = list(self._columns.items())
		# if len(list(filter(lambda x: "PRIMARY" in str(x), list(zip(*items))[1]))) > 1:
		# 	for item in items:
		# 		if "PRIMARY" in str(item[1]):
		# 			self.__dict__.pop(item[0])
		# 			items = list(self.__dict__.items())
		# 			break
		# print("------------------------------------------------------------\n", items, "\n------------------------------------------------------------")
		if self._pprint:
			append = "\n\t"
		else:
			append = ""
		out = f"CREATE TABLE {self._name} (" + append
		for name, _type in items:
			if isinstance(_type, tuple):
				_type, name = _type
			out += f"{name} {_type}, " + append
		for foreign_key in self._foreign_keys:
			for ref in self._foreign_keys[foreign_key]:
				out += f"FOREIGN KEY ({foreign_key}) REFERENCES {ref}, " + append
		return out.strip(", " + append) + ");"
