package com.codeturret.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "snowflake")
@Data
public class SnowflakeProperties {
    private String account;
    private String user;
    private String password;
    private String warehouse = "CODEBOUNCER_WH";
    private String database = "CODEBOUNCER";
    private String schema = "CORE";
    private String cortexModel = "llama3.1-8b";

    public boolean isConfigured() {
        return account != null && !account.isBlank()
            && user != null && !user.isBlank()
            && password != null && !password.isBlank();
    }
}
