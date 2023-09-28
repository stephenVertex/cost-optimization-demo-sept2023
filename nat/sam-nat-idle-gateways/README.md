# sam-nat-idle-gateways

This folder contains a simple SAM app to have a lambda function which runs an Athena query for idle NAT gateways.


# Making it run on a schedule

Add the following block of yaml to the end of a function

```yaml
      Events:
        MyScheduledEvent:
          Type: Schedule
          Properties:
            Schedule: 'cron(0 10 * * ? *)'

```
