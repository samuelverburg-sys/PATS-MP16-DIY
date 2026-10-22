# Host tests for the platform-free core (firmware/libraries/MP16/src/core). Run: make -C firmware/test
CORE := ../libraries/MP16/src/core
CXX ?= g++
CXXFLAGS ?= -std=gnu++17 -Wall -Wextra -Werror -g -fsanitize=address,undefined -fno-sanitize-recover=all

test_core: test_core.cpp $(wildcard $(CORE)/*.cpp) $(wildcard $(CORE)/*.h)
	$(CXX) $(CXXFLAGS) -o $@ test_core.cpp $(wildcard $(CORE)/*.cpp)
	./$@

.PHONY: clean
clean:
	rm -f test_core
