package main

import (
	"os"
)

func check(e error) {
	if e != nil {
		panic(e)
	}
}

func readConfig(loc string) []byte {
	dat, err := os.ReadFile(loc)
	check(err)
	return dat
}
