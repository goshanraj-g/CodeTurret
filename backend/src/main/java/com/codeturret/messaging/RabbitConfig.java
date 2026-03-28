package com.codeturret.messaging;

import org.springframework.amqp.core.*;
import org.springframework.amqp.rabbit.connection.ConnectionFactory;
import org.springframework.amqp.rabbit.core.RabbitAdmin;
import org.springframework.amqp.support.converter.Jackson2JsonMessageConverter;
import org.springframework.amqp.support.converter.MessageConverter;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class RabbitConfig {

    // -- Exchange names -------------------------------------------------------
    public static final String SCAN_REQUESTS_EXCHANGE  = "scan.requests";
    public static final String FIX_REQUESTS_EXCHANGE   = "fix.requests";
    public static final String SCAN_PROGRESS_EXCHANGE  = "scan.progress";

    // -- Queue names ----------------------------------------------------------
    public static final String SCAN_QUEUE = "scan.queue";
    public static final String FIX_QUEUE  = "fix.queue";

    // -- Routing keys ---------------------------------------------------------
    public static final String SCAN_ROUTING_KEY = "scan";
    public static final String FIX_ROUTING_KEY  = "fix";

    // -- Exchanges ------------------------------------------------------------

    @Bean
    public DirectExchange scanRequestsExchange() {
        return new DirectExchange(SCAN_REQUESTS_EXCHANGE, true, false);
    }

    @Bean
    public DirectExchange fixRequestsExchange() {
        return new DirectExchange(FIX_REQUESTS_EXCHANGE, true, false);
    }

    @Bean
    public TopicExchange scanProgressExchange() {
        return new TopicExchange(SCAN_PROGRESS_EXCHANGE, true, false);
    }

    // -- Queues ---------------------------------------------------------------

    @Bean
    public Queue scanQueue() {
        return QueueBuilder.durable(SCAN_QUEUE).build();
    }

    @Bean
    public Queue fixQueue() {
        return QueueBuilder.durable(FIX_QUEUE).build();
    }

    // -- Bindings -------------------------------------------------------------

    @Bean
    public Binding scanQueueBinding() {
        return BindingBuilder.bind(scanQueue()).to(scanRequestsExchange()).with(SCAN_ROUTING_KEY);
    }

    @Bean
    public Binding fixQueueBinding() {
        return BindingBuilder.bind(fixQueue()).to(fixRequestsExchange()).with(FIX_ROUTING_KEY);
    }

    // -- Message converter (JSON) --------------------------------------------

    @Bean
    public MessageConverter jsonMessageConverter() {
        return new Jackson2JsonMessageConverter();
    }

    @Bean
    public RabbitAdmin rabbitAdmin(ConnectionFactory connectionFactory) {
        return new RabbitAdmin(connectionFactory);
    }
}
