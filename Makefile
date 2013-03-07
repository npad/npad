SUBDIRS = diag_server pathdiag
RECURSIVE_TARGETS = all-recursive clean-recursive install-recursive

all: all-recursive

clean: clean-recursive
	# ./config.py droppings
	rm -f Makefile.config  DiagServerConfig.py diag_form.html npad


$(RECURSIVE_TARGETS):
	@target=`echo $@ | sed s/-recursive//`; \
	list='$(SUBDIRS)'; for subdir in $$list; do \
		(cd $$subdir && $(MAKE) $$target); \
	done

-include Makefile.config

install: all
	@echo
	@groupadd $(GROUP) >/dev/null 2>&1; RES=$$?; \
	if [ "$$RES" = "0" ]; then \
		echo "Added group $(GROUP)"; \
	elif [ "$$RES" = "9" ]; then \
		echo "Group $(GROUP) already exists.  Will not create."; \
	else \
		echo "Error creating group $(GROUP)"; \
		exit $$RES; \
	fi
	@echo
	@useradd -c "NPAD User" -g $(GROUP) -d /nonexistent -s /bin/false $(USER) >/dev/null 2>&1; RES=$$?; \
	if [ "$$RES" = "0" ]; then \
		echo "Added user $(USER)"; \
	elif [ "$$RES" = "9" ]; then \
		echo "User $(USER) already exists.  Will not create."; \
	else \
		echo "Error creating user $(USER)"; \
		exit $$RES; \
	fi
	@echo
	@if [ -z "$(EXEC_DIR)" ]; then \
		echo "You need to run the config script before installing."; \
		echo "See the INSTALL document in the distribution for more information."; \
		exit 1; \
	fi
	@echo -e "Installing...\n"
	@if [ ! -d "$(EXEC_DIR)" ]; then \
		echo "Creating directory: $(EXEC_DIR)"; \
		mkdir -p "$(EXEC_DIR)"; \
	fi; \
	if [ ! -d "$(WWW_DIR)" ]; then \
		echo "Creating directory: $(WWW_DIR)"; \
		mkdir -p "$(WWW_DIR)"; \
	fi; \
	if [ ! -d "$(LOGDIR)" ]; then \
		echo "Creating directory: $(LOGDIR)"; \
		mkdir "$(LOGDIR)"; \
		chmod 1777 "$(LOGDIR)"; \
	fi; \
	cp diag_form.html "$(WWW_DIR)"
	@if [ -e "$(WWW_DIR)/index.html" ]; then \
		if cmp "$(WWW_DIR)/index.html" "$(WWW_DIR)/diag_form.html"; then \
			true; \
		else \
			echo -e "\nWARNING: index.html does not point to diag_form.html.\n"; \
		fi; \
	else \
		( cd "$(WWW_DIR)"; ln -s diag_form.html index.html ); \
	fi
	rm -f $(EXEC_DIR)/config.xml $(EXEC_DIR)/template_diag_form.html
	cp config.xml template_diag_form.html $(EXEC_DIR)/
	@$(MAKE) install-recursive
	sudo chown -R $(USER).$(GROUP) "$(LOGDIR)"   # MLab specific
