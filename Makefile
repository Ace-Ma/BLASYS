all : _asso.so clean

CC = gcc
CFLAGS = -O2 -fPIC -c -std=c99
SFLAGS = -shared
ifeq ($(shell uname -s | tr A-Z a-z),darwin)
SFLAGS += -undefined dynamic_lookup
ENV=$(shell python3-config --cflags)
else
ENV=$(shell python3-config --cflags | cut -d " " -f1)
endif

ifeq ($(ENV),)
$(error Cannot find Python environment.,,)
endif

_asso.so: asso/asso_wrap.c asso/driver.c asso/utils.c asso/approx.c
	@$(CC) $(CFLAGS) asso/asso_wrap.c $(ENV)
	@$(CC) $(CFLAGS) asso/driver.c asso/utils.c asso/approx.c
	@$(CC) $(SFLAGS) *.o -o utils/_asso.so

clean:
	@rm -f *.o
