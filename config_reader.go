package main

import (
	"os"
)

func check(e error) {
	if e != nil {
		panic(e)
	}
}

func readConfig() []byte {
	dat, err := os.ReadFile("config.yml")
	check(err)
	return dat
}
