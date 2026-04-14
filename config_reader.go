package main

import (
	"os"

	log "github.com/sirupsen/logrus"
	yaml "gopkg.in/yaml.v3"
)

// fatalf allows tests to override fatal behavior. In production, it maps to log.Fatalf.
var fatalf = log.Fatalf

// check logs a fatal error and exits if err is non-nil.
func check(e error) {
	if e != nil {
		fatalf("%v", e)
	}
}

// readConfig reads the YAML configuration file at loc and returns its raw bytes.
func readConfig(loc string) []byte {
	dat, err := os.ReadFile(loc)
	check(err)
	return dat
}

// parseConfig unmarshals YAML bytes into []Config.
func parseConfig(data []byte) ([]Config, error) {
	var cfg []Config
	if err := yaml.Unmarshal(data, &cfg); err != nil {
		return nil, err
	}
	return cfg, nil
}
