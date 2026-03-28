package com.codeturret;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;

@SpringBootApplication
@ConfigurationPropertiesScan
public class CodeTurretApplication {
    public static void main(String[] args) {
        SpringApplication.run(CodeTurretApplication.class, args);
    }
}
