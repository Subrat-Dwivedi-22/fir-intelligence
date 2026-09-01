from worker.pipeline import FIRPipeline


pipeline = FIRPipeline()


def start_fir_processing(
    message: dict,
):

    pipeline.process(
        job_id=message["job_id"],
        case_id=message["case_id"],
        document_id=message["document_id"],
        s3_key=message["s3"]["key"],
    )