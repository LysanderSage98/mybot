import typing


class _GetItem:

	def __init__(self, getitem):
		self._getitem = getitem
		self.__name__ = repr(getitem)
		self.__base__ = ...

	def __call__(self, name, data):
		temp = self._getitem(name, data)
		return temp

	def __getitem__(self, item):
		if isinstance(item, tuple):
			name = item[0]
			temp: CollectionAccess = self._getitem.get_coll(name)
			temp.set_other(other_args = item[1:])
			return temp
		else:
			return self._getitem.get_coll(item)

	def __str__(self):  # todo update if collections hold other things besides string types
		return "str"


class CollectionAccess:
	def __init__(self, name, data):
		self.name = name
		self.data = data
		self.__origin__ = typing.Literal
		self._checked_orig = False
		self._other = None
		self._other_args = []
		self.___args__ = ...

	def set_other(self, other_args):
		if None in other_args:
			self._other = typing.Union
			del self.__origin__
			self._other_args.extend(other_args[1:])
		else:
			self._other_args.extend(other_args)

	def __getattribute__(self, item):
		if item == "__origin__" and self._other:
			if self._checked_orig:
				return self._other
			else:
				self._checked_orig = True
		elif item == "__args__" and self._other and self._checked_orig:
			# noinspection PyTypeHints
			temp = [typing.Literal[tuple(super().__getattribute__(item))], type(None)]
			return temp
		return super().__getattribute__(item)

	def __str__(self):
		if self._other:
			other = ", None"
		else:
			other = ""
		other_args = ", '" + "', '".join(map(str, self._other_args)) + "'" if self._other_args else ""
		return f"Collection['{self.name}'{other}{other_args}]"

	@property
	def __args__(self):
		temp = []
		for key, val in self.data.items():
			if isinstance(val, tuple) and len(val) >= 2:  # should only be important for command list
				if not val[1]:
					temp.append(key)
			else:
				temp.append(key)
		if self._other_args:
			for arg in self._other_args:
				if isinstance(arg, CollectionAccess):
					temp.extend(arg.__args__)
				else:
					temp.append(arg)
		return temp


@_GetItem
class Collection:
	__all = {}

	def __new__(cls, name, data):
		instance = super().__new__(cls)
		cls.__all.update({name: instance})
		return instance

	@classmethod
	def get_coll(cls, name):
		suffixes = ["", "s", "es"]
		for suffix in suffixes:
			if temp := cls.__all.get(name + suffix):
				break
		else:
			temp = None
		if temp:
			return CollectionAccess(name, temp.data)
		else:
			return None

	def __init__(self, name, data):
		self.name = name
		self.data = data
