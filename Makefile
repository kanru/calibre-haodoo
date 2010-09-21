haodoo_SOURCE = haodoo/plugin.py

haodoo.zip: $(haodoo_SOURCE)
	zip haodoo.zip $(haodoo_SOURCE)

all: haodoo.zip
