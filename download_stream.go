package main

import (
	"bytes"
	"os"

	fluentffmpeg "github.com/modfy/fluent-ffmpeg"
)

func downloadStream(user string, url string, control chan bool, response chan bool) {
	buf := &bytes.Buffer{}
	cmd := fluentffmpeg.NewCommand("").InputPath(url).OutputFormat("mp4").OutputPath(user + ".mp4").Overwrite(true).OutputLogs(buf).Build()
	cmd.Start()

	for {
		_, more := <-control
		if !more {
			cmd.Process.Signal(os.Interrupt)
			response <- true
		}
	}
}
