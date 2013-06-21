PYVERSION=2.7
haystack:	haystack.py
				cython -D --embed haystack.py -o haystack.c
				$(CC) -I /usr/include/python$(PYVERSION) haystack.c -lpython$(PYVERSION) -o haystack
