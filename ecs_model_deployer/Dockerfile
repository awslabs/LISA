FROM public.ecr.aws/lambda/nodejs:18

COPY ./dist/ ${LAMBDA_TASK_ROOT}
RUN chmod 777 -R ${LAMBDA_TASK_ROOT}
CMD ["index.handler"]
