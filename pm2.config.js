module.exports = {
    apps: [{
        name:           "mnq-bridge",
        script:         "dxfeed_bridge.js",
        cwd:            "C:\\Users\\ryadb\\OneDrive\\QUANT MATHS",
        restart_delay:  3000,   // attend 3s avant de redémarrer
        max_restarts:   99999,  // redémarre indéfiniment
        autorestart:    true,
        watch:          false,
        log_date_format:"YYYY-MM-DD HH:mm:ss",
        out_file:       "C:\\tmp\\bridge.log",
        error_file:     "C:\\tmp\\bridge_err.log",
    }]
};
