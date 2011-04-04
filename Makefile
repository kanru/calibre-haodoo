haodoo_SOURCE = COPYING README.markdown __init__.py

haodoo.zip: $(haodoo_SOURCE)
	zip haodoo.zip $(haodoo_SOURCE)

all: haodoo.zip
