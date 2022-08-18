package main

import (
	"os"

	log "github.com/sirupsen/logrus"
)

func check(e error) {
	if e != nil {
		log.Fatalf("%v", e)
		panic(e)
	}
}

func readConfig(loc string) []byte {
	dat, err := os.ReadFile(loc)
	check(err)
	return dat
}
