FROM public.ecr.aws/lambda/nodejs:18

COPY ./dist/ ${LAMBDA_TASK_ROOT}
RUN chmod 777 --recursive ${LAMBDA_TASK_ROOT}
CMD ["vector_store_deployer/src/index.handler"]
