import random
import operator

from . import storage
from .core import command


class Lexicon(storage.SelectableStorage):
	lib = 'pmx'

	@classmethod
	def initialize(cls):
		cls.store = cls.from_URI()
		cls._finalizers.append(cls.finalize)

	@classmethod
	def finalize(cls):
		del cls.store

	@staticmethod
	def split_num(lookup):
		prefix, sep, num = lookup.rpartition(' ')
		if not prefix or not num.isdigit():
			return lookup, 0
		return prefix, int(num)

	def lookup(self, rest=''):
		rest = rest.strip()
		return self.lookup_with_num(*self.split_num(rest))


class SQLiteLexicon(Lexicon, storage.SQLiteStorage):
	def init_tables(self):
		CREATE_LEXICON_TABLE = '''
			CREATE TABLE
			IF NOT EXISTS lexicon (
				lexiconid INTEGER NOT NULL,
				library VARCHAR NOT NULL,
				term TEXT NOT NULL,
				PRIMARY KEY (lexiconid)
			)
			'''
		CREATE_LEXICON_INDEX = '''
			CREATE INDEX
			IF NOT EXISTS ix_lexicon_library
			on lexicon(library)
			'''
		self.db.execute(CREATE_LEXICON_TABLE)
		self.db.execute(CREATE_LEXICON_INDEX)
		self.db.commit()

	def lookup_with_num(self, thing='', num=0):
		lib = self.lib
		BASE_SEARCH_SQL = """
			SELECT lexiconid, term
			FROM lexicon
			WHERE library = ? %s order by lexiconid
			"""
		thing = thing.strip().lower()
		num = int(num)
		if thing:
			wtf = (
				' AND %s' % (
					' AND '.join(
						["term like '%%%s%%'" % x for x in thing.split()]
					)
				)
			)
			SEARCH_SQL = BASE_SEARCH_SQL % wtf
		else:
			SEARCH_SQL = BASE_SEARCH_SQL % ''
		results = [x[1] for x in self.db.execute(SEARCH_SQL, (lib,)).fetchall()]
		n = len(results)
		if n > 0:
			if num:
				i = num - 1
			else:
				i = random.randrange(n)
			quote = results[i]
		else:
			i = 0
			quote = ''
		return (quote, i + 1, n)

	def add(self, term):
		lib = self.lib
		term = term.strip()
		if not term:
			# Do not add empty quotes
			return
		ADD_LEXICON_SQL = 'INSERT INTO lexicon (library, term) VALUES (?, ?)'
		res = self.db.execute(ADD_LEXICON_SQL, (lib, term,))
		self.db.commit()

	def __iter__(self):
		# Note: also filter on quote not null, for backward compatibility
		query = "SELECT term FROM lexicon WHERE library = ? and term is not null"
		for row in self.db.execute(query, [self.lib]):
			yield {'text': row[0]}


@command(aliases=("lex","define", "def",))
def lexicon(rest):
	"""
	If passed with nothing then get a random quote. If passed with some
	string then search for that. If prepended with "add:" then add it to the
	db, eg "!quote add: drivers: I only work here because of pmxbot!".
	Delete an individual quote by prepending "del:" and passing a search
	matching exactly one query.
	"""
	rest = rest.strip()
	if rest.startswith('del: ') or rest.startswith('del '):
		cmd, sep, lookup = rest.partition(' ')
		Lexicon.store.delete(lookup)
		return 'Deleted the sole term that matched'
	if rest.startswith('add: ') or rest.startswith('add '):
		term_to_add = rest.split(' ', 1)[1]
		Lexicon.store.add(term_to_add)
		qt = False
		return 'Term added!'
	return "lex, def, define are used for adding (add) or deleting (del) terms. To lookup a term use \"whatis\"";

@command(aliases="whatis")
def whatis(rest):
	"""
	If passed with nothing then get a random quote. If passed with some
	string then search for that. 
	"""
	qt, i, n = Lexicon.store.lookup(rest)
	if not qt:
		return
	return '(%s/%s): %s' % (i, n, qt)
